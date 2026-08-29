# consumers.py

import json
import random
import asyncio
import math
from channels.generic.websocket import AsyncWebsocketConsumer

# 【全局内存房间数据】
GAME_ROOMS = {}

class SnakeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'snake_{self.room_name}'
        
        # 【关键修复 1】延迟导入 User 模型，解决 AppRegistryNotReady 报错
        from django.contrib.auth.models import User 
        
        # 1. 获取用户信息
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return

        # 2. 加入频道组
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # 3. 初始化或加入房间逻辑
        if self.room_name not in GAME_ROOMS:
            GAME_ROOMS[self.room_name] = {
                'snakes': [], 
                'foods': [],
                'players': {}, 
                'loop_task': None
            }
            print(f"🆕 创建新房间: {self.room_name}")
        
        room_data = GAME_ROOMS[self.room_name]
        
        # 先把当前玩家注册到房间的玩家列表里
        room_data['players'][self.channel_name] = self.user
        
        # 4. 启动游戏循环 (带锁机制，防止多开)
        if room_data['loop_task'] is None or room_data['loop_task'].done():
            print(f"🚀 准备启动房间 {self.room_name} 的游戏循环...")
            room_data['loop_task'] = asyncio.create_task(self.game_loop(self.room_name))
        else:
            print(f"ℹ️ 房间 {self.room_name} 游戏循环已在运行中，玩家 {self.user.username} 直接加入。")

        # 5. 如果这条蛇还不存在，立刻创建它
        existing_snake = next((s for s in room_data['snakes'] if s['id'] == str(self.user.id)), None)
        
        if not existing_snake:
            new_snake = {
                'id': str(self.user.id), # 统一使用字符串类型的 User ID
                'owner_channel': self.channel_name, 
                'name': self.user.username,
                'body': [{'x': random.randint(5, 15), 'y': random.randint(5, 15)}],
                'dx': 1, 'dy': 0,
                'alive': True,
                'score': 0
            }
            room_data['snakes'].append(new_snake)
            print(f"🐍 玩家 {self.user.username} 的蛇已生成")

        # 6. 创建蛇后再发送首帧，保证首次进入即可看到并控制自己的蛇
        await self.send(text_data=json.dumps({
            'type': 'update_game',
            'snakes': room_data['snakes'],
            'foods': room_data['foods'],
            'my_id': str(self.user.id)
        }))

    async def disconnect(self, close_code):
        # 离开频道组
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # 从房间玩家列表中移除
        room_data = GAME_ROOMS.get(self.room_name)
        if room_data and self.channel_name in room_data['players']:
            del room_data['players'][self.channel_name]
            
        # 如果房间空了，清理内存
        if room_data and not room_data['players']:
            if room_data['loop_task'] and not room_data['loop_task'].done():
                room_data['loop_task'].cancel()
            del GAME_ROOMS[self.room_name]
            print(f"🧹 房间 {self.room_name} 已清空并销毁")

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('type')
        room_data = GAME_ROOMS.get(self.room_name)

        if not room_data: return

        # 1. 移动逻辑
        if action == 'move':
            direction = data.get('direction')
            my_snake = next((s for s in room_data['snakes'] if s['id'] == str(self.user.id)), None)
            
            if my_snake and my_snake['alive']:
                if direction == 'up' and my_snake['dy'] != 1:
                    my_snake['dx'], my_snake['dy'] = 0, -1
                elif direction == 'down' and my_snake['dy'] != -1:
                    my_snake['dx'], my_snake['dy'] = 0, 1
                elif direction == 'left' and my_snake['dx'] != 1:
                    my_snake['dx'], my_snake['dy'] = -1, 0
                elif direction == 'right' and my_snake['dx'] != -1:
                    my_snake['dx'], my_snake['dy'] = 1, 0
                    
        # 2. 【新增】重新开始逻辑
        elif action == 'restart':
            my_snake = next((s for s in room_data['snakes'] if s['id'] == str(self.user.id)), None)
            if my_snake:
                my_snake['alive'] = True
                my_snake['body'] = [{'x': random.randint(5, 15), 'y': random.randint(5, 15)}]
                my_snake['dx'], my_snake['dy'] = 1, 0
                my_snake['score'] = 0
                print(f"🔄 玩家 {self.user.username} 重新开始游戏")
            
            # 如果游戏循环因为全灭停止了，需要重启它
            if room_data['loop_task'] is None or room_data['loop_task'].done():
                room_data['loop_task'] = asyncio.create_task(self.game_loop(self.room_name))

    # 【新增】广播状态给当前玩家
    async def broadcast_state(self, event):
        await self.send(text_data=json.dumps({
            'type': 'update_game',
            'snakes': event['snakes'],
            'foods': event['foods'],
            'my_id': str(self.user.id) # 【关键修复 3】确保每次广播都带上自己的 ID
        }))

    async def game_loop(self, room_name):
        print(f"🔄 游戏循环正式开始: {room_name}")
        try:
            while True:
                await asyncio.sleep(0.2) 
                
                # 1. 安全检查：房间还在吗？
                if room_name not in GAME_ROOMS:
                    break
                    
                room_data = GAME_ROOMS[room_name]
                
                # 2. 安全检查：没人了还跑什么？
                if not room_data['players']:
                    print(f"⚠️ 房间 {room_name} 没人了，停止循环")
                    break

                grid_size = 30 

                # 3. 移动所有活着的蛇
                for snake in room_data['snakes']:
                    if not snake.get('alive', False): 
                        continue
                    
                    head = snake['body'][0]
                    new_head = {'x': head['x'] + snake['dx'], 'y': head['y'] + snake['dy']}
                    
                    # 撞墙检测
                    if not (0 <= new_head['x'] < grid_size and 0 <= new_head['y'] < grid_size):
                        snake['alive'] = False
                        print(f"💀 蛇 {snake['name']} 撞墙死亡")
                        continue
                        
                    snake['body'].insert(0, new_head)
                    
                    # 吃食物
                    ate_food = False
                    for i in range(len(room_data['foods']) - 1, -1, -1):
                        food = room_data['foods'][i]
                        if new_head['x'] == food['x'] and new_head['y'] == food['y']:
                            room_data['foods'].pop(i)
                            snake['score'] += 1
                            ate_food = True
                            break 
                    
                    if not ate_food:
                        snake['body'].pop()

                # 4. 补充食物
                while len(room_data['foods']) < 5:
                    room_data['foods'].append({
                        'x': random.randint(0, grid_size - 1),
                        'y': random.randint(0, grid_size - 1)
                    })

                # 5. 判断游戏结束 (所有蛇都死了)
                alive_count = sum(1 for s in room_data['snakes'] if s['alive'])
                total_count = len(room_data['snakes'])
                
                if total_count > 0 and alive_count == 0:
                    print(f"🏁 房间 {room_name} 所有蛇死亡，游戏结束")
                    # 广播游戏结束消息给前端
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {'type': 'game_over_message', 'message': '所有玩家均已阵亡！'}
                    )
                    break 

                # 6. 广播状态
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'broadcast_state',
                        'snakes': room_data['snakes'],
                        'foods': room_data['foods']
                    }
                )
                
        except Exception as e:
            print(f"❌ 游戏循环发生严重错误: {e}")
            import traceback
            traceback.print_exc()

    # 【新增】处理游戏结束消息
    async def game_over_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_over',
            'message': event['message']
        }))

# game/consumers.py

# consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ForestProgress, GamePlayer, GameRoom

IRON_GAME_STATES = {}
IRON_GAME_LOOPS = {}

ROLE_STARTS = {
    GamePlayer.ROLE_WU_XIE: {"x": 90, "y": 540},
    GamePlayer.ROLE_XIAOGE: {"x": 140, "y": 540},
    GamePlayer.ROLE_PANGZI: {"x": 190, "y": 540},
}

FOREST_PLATFORMS = [
    {"x": 0, "y": 600, "w": 1200, "h": 50},
    {"x": 250, "y": 500, "w": 190, "h": 24},
    {"x": 510, "y": 430, "w": 150, "h": 24},
    {"x": 720, "y": 520, "w": 150, "h": 24},
    {"x": 900, "y": 390, "w": 170, "h": 24},
    {"x": 1040, "y": 280, "w": 160, "h": 24},
]
FOREST_HAZARDS = [{"x": 450, "y": 580, "w": 60, "h": 20}]
SECOND_LEVEL_PLATFORMS = [
    {"x": 0, "y": 600, "w": 270, "h": 50},
    {"x": 340, "y": 540, "w": 180, "h": 24},
    {"x": 590, "y": 470, "w": 170, "h": 24},
    {"x": 820, "y": 390, "w": 170, "h": 24},
    {"x": 1030, "y": 600, "w": 170, "h": 50},
]
SECOND_LEVEL_HAZARDS = [
    {"x": 270, "y": 620, "w": 70, "h": 30},
    {"x": 520, "y": 620, "w": 70, "h": 30},
    {"x": 760, "y": 620, "w": 70, "h": 30},
    {"x": 990, "y": 620, "w": 40, "h": 30},
]
THIRD_LEVEL_PLATFORMS = [
    # 连续底层保证战斗不被断崖卡住，上层形成可自由穿梭的立体路线。
    {"x": 0, "y": 600, "w": 1200, "h": 50},
    {"x": 185, "y": 505, "w": 175, "h": 22},
    {"x": 415, "y": 415, "w": 155, "h": 22},
    {"x": 625, "y": 500, "w": 170, "h": 22},
    {"x": 855, "y": 405, "w": 160, "h": 22},
    {"x": 1025, "y": 510, "w": 120, "h": 22},
]
FOURTH_LEVEL_PLATFORMS = [
    {"x": 0, "y": 600, "w": 205, "h": 50},
    {"x": 275, "y": 535, "w": 165, "h": 22},
    {"x": 650, "y": 455, "w": 140, "h": 22},
    {"x": 790, "y": 360, "w": 140, "h": 22},
    {"x": 1060, "y": 600, "w": 140, "h": 50},
    # 两条可选的高层支路，让三个人不必挤在同一条线上。
    {"x": 90, "y": 465, "w": 105, "h": 20},
    {"x": 945, "y": 470, "w": 85, "h": 20},
]
FOURTH_LEVEL_HAZARDS = [
    {"x": 205, "y": 620, "w": 70, "h": 30},
    {"x": 440, "y": 620, "w": 210, "h": 30},
    {"x": 790, "y": 620, "w": 270, "h": 30},
]


class IronTriangleConsumer(AsyncWebsocketConsumer):
    
    async def connect(self):
        # 1. 获取房间信息
        self.room_id = str(self.scope['url_route']['kwargs']['room_id'])
        self.room_group_name = f'game_room_{self.room_id}'
        
        # 2. 只允许已经通过邀请加入数据库房间的用户连接
        user = self.scope.get("user")
        if not user or user.is_anonymous or not await self.is_room_player(user.id):
            await self.close(code=4403)
            return
        self.username = user.username
        
        # 3. 加入频道组并接受连接
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        room_status = await self.get_room_status()
        has_active_game = self.room_id in IRON_GAME_STATES
        if room_status == 'playing' and has_active_game:
            self.ensure_game_loop()
        await self.broadcast_room_info()
        if room_status == 'playing' and has_active_game:
            await self.send_game_state()
        elif room_status == 'playing':
            await self.send(text_data=json.dumps({
                'type': 'level_select',
                'unlocked_level': await self.get_room_unlocked_level(),
                'is_host': self.scope['user'].id == await self.get_host_id(),
            }))

    async def disconnect(self, close_code):
        # 1. 离开频道组
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        
        # 离线不会删除玩家席位，刷新页面后仍可回到原房间。
        await self.broadcast_room_info()

    async def receive(self, text_data):
        """接收前端消息"""
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'start_game':
            can_start = await self.can_start_game()
            if not can_start:
                await self.send(text_data=json.dumps({
                    'type': 'error', 'message': '只有房主能在三人到齐后开启机关。'
                }))
                return
            unlocked_level = await self.get_room_unlocked_level()
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'level_select', 'unlocked_level': unlocked_level}
            )
        elif action == 'select_level':
            level = data.get('level')
            unlocked_level = await self.get_room_unlocked_level()
            if not await self.is_host() or not isinstance(level, int) or level < 1 or level > min(4, unlocked_level):
                await self.send(text_data=json.dumps({'type': 'error', 'message': '该关卡尚未解锁'}))
                return
            await self.ensure_game_state(reset=True)
            state = IRON_GAME_STATES[self.room_id]
            if level == 2:
                self._load_second_level(state)
            elif level == 3:
                self._load_third_level(state)
            elif level == 4:
                self._load_fourth_level(state)
            state['paused'] = False
            self.ensure_game_loop(restart=True)
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'game_start', 'room_id': self.room_id}
            )
            await self.broadcast_game_state(full=True)
        elif action == 'pause':
            state = IRON_GAME_STATES.get(self.room_id)
            if state:
                state['paused'] = True
                for player in state['players'].values():
                    player['input'] = {'left': False, 'right': False}
                unlocked_level = await self.get_room_unlocked_level()
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {'type': 'level_select', 'unlocked_level': unlocked_level}
                )
        elif action == 'input':
            state = IRON_GAME_STATES.get(self.room_id)
            if not state:
                return
            player = state['players'].get(str(self.scope['user'].id))
            if not player:
                return
            player['input']['left'] = bool(data.get('left'))
            player['input']['right'] = bool(data.get('right'))
            can_double_jump = (
                player['role'] == GamePlayer.ROLE_XIAOGE
                and player['jumps_remaining'] > 0
            )
            if data.get('jump') and (player['grounded'] or can_double_jump):
                player['vy'] = -17 if player['role'] == GamePlayer.ROLE_XIAOGE else (-12 if player['role'] == GamePlayer.ROLE_PANGZI else -14)
                player['grounded'] = False
                player['jumps_remaining'] = max(0, player['jumps_remaining'] - 1)
        elif action == 'swing':
            state = IRON_GAME_STATES.get(self.room_id)
            player = state and state['players'].get(str(self.scope['user'].id))
            if not player or state['level'] != 4:
                return
            attached_rope_id = player.get('attached_rope')
            attached_rope = next(
                (rope for rope in state['swing_ropes'] if rope['id'] == attached_rope_id),
                None,
            )
            available_ropes = [
                rope for rope in state['swing_ropes']
                if rope.get('rider') is None
                and (player['x'] + 16 - rope['x']) ** 2
                + (player['y'] + 24 - rope['y']) ** 2 <= 90 ** 2
            ]
            if attached_rope:
                self._release_swing_rope(state, player, attached_rope)
                state['notice'] = f"{player['username']} 松开绳索，借着惯性飞向对岸"
            elif available_ropes:
                rope = min(
                    available_ropes,
                    key=lambda item: (player['x'] + 16 - item['x']) ** 2
                    + (player['y'] + 24 - item['y']) ** 2,
                )
                rope['rider'] = player['id']
                player['attached_rope'] = rope['id']
                player['vx'] = player['vy'] = 0
                player['grounded'] = False
                state['notice'] = f"{player['username']} 抓住绳索，按 A/D 加力，再按 Q 松手"
            else:
                state['notice'] = '这里够不到绳头，再靠近一些按 Q'
            await self.broadcast_game_state()
        elif action == 'interact':
            state = IRON_GAME_STATES.get(self.room_id)
            player = state and state['players'].get(str(self.scope['user'].id))
            if not player:
                return
            if state['level'] == 4:
                objectives = state['level4_objectives']
                if (
                    player['role'] == GamePlayer.ROLE_PANGZI
                    and self._near(player, state['counterweight'], 80)
                    and not objectives['counterweight']
                ):
                    objectives['counterweight'] = True
                    state['notice'] = f"{player['username']} 压下配重，悬宫深处的升降台开始运转"
                elif (
                    player['role'] == GamePlayer.ROLE_XIAOGE
                    and self._near(player, state['sky_lever'], 80)
                    and objectives['counterweight']
                    and not objectives['sky_lever']
                ):
                    objectives['sky_lever'] = True
                    state['notice'] = f"{player['username']} 启动天梁，通往星盘的悬桥已经接通"
                elif (
                    player['role'] == GamePlayer.ROLE_WU_XIE
                    and self._near(player, state['astrolabe'], 80)
                    and objectives['sky_lever']
                    and not objectives['astrolabe']
                ):
                    await self.send(text_data=json.dumps({
                        'type': 'astrolabe_open',
                        'tiles': state['astrolabe_puzzle']['tiles'],
                    }))
                    state['notice'] = f"{player['username']} 正在校准四象星盘"
                elif not objectives['counterweight']:
                    state['notice'] = '沉重的配重机关只能由胖子启动'
                elif not objectives['sky_lever']:
                    state['notice'] = '天梁机关位于高处，需要张起灵前往'
                elif not objectives['astrolabe']:
                    state['notice'] = '最后的四象星盘只有吴邪能看懂'
                else:
                    state['notice'] = '悬宫机关已经全部归位，前往出口'
            elif (
                state['level'] == 2
                and player['role'] == GamePlayer.ROLE_XIAOGE
                and self._near(player, state['rope']['anchor'], 85)
            ):
                pangzi = next(
                    (p for p in state['players'].values() if p['role'] == GamePlayer.ROLE_PANGZI),
                    None,
                )
                if pangzi and not state['rope']['deployed']:
                    state['rope']['deployed'] = True
                    state['rope']['pulling'] = True
                    state['rope']['completed'] = False
                    state['rope']['start_x'] = pangzi['x']
                    state['rope']['start_y'] = pangzi['y']
                    state['rope']['progress'] = 0
                    pangzi['input'] = {'left': False, 'right': False}
                    pangzi['vx'] = pangzi['vy'] = 0
                    state['notice'] = f"{player['username']} 放下绳索，正在把胖子拉过断崖"
                else:
                    state['notice'] = '绳索已经固定好了'
            elif (
                state['level'] == 2
                and player['role'] == GamePlayer.ROLE_PANGZI
                and state['rope']['deployed']
            ):
                self._detach_level_two_rope(state, player)
                state['notice'] = f"{player['username']} 主动解开了绳子"
            elif state['level'] == 2:
                state['notice'] = '张起灵需要到达对岸绳桩，按 E 放下绳索'
            elif state['level'] == 3:
                return
            elif player['role'] == GamePlayer.ROLE_WU_XIE and self._near(player, state['console']):
                await self.send(text_data=json.dumps({
                    'type': 'puzzle_open',
                    'tiles': state['puzzle']['tiles'],
                }))
                state['notice'] = f"{player['username']} 正在破解青铜拼图"
            elif player['role'] == GamePlayer.ROLE_XIAOGE and self._near(player, state['lever']):
                state['objectives']['lever'] = True
                state['notice'] = f"{player['username']} 拉下了高处机关"
            elif player['role'] == GamePlayer.ROLE_PANGZI and self._near(player, state['crate'], 75):
                state['notice'] = "胖子需要用身体把石箱推到发光踏板上"
            else:
                state['notice'] = "这里没有你能操作的机关"
            await self.broadcast_game_state()
        elif action == 'puzzle_submit':
            state = IRON_GAME_STATES.get(self.room_id)
            player = state and state['players'].get(str(self.scope['user'].id))
            tiles = data.get('tiles')
            valid = (
                player and player['role'] == GamePlayer.ROLE_WU_XIE
                and state['level'] == 1 and self._near(player, state['console'])
                and isinstance(tiles, list) and len(tiles) == 4
                and all(isinstance(tile, int) and tile % 4 == 0 for tile in tiles)
            )
            if valid:
                state['puzzle']['tiles'] = [0, 0, 0, 0]
                state['objectives']['console'] = True
                state['notice'] = f"{player['username']} 拼合了完整的青铜兽面"
            else:
                await self.send(text_data=json.dumps({'type': 'puzzle_error', 'message': '图案仍有错位'}))
            await self.broadcast_game_state()
        elif action == 'astrolabe_submit':
            state = IRON_GAME_STATES.get(self.room_id)
            player = state and state['players'].get(str(self.scope['user'].id))
            tiles = data.get('tiles')
            valid = (
                player and player['role'] == GamePlayer.ROLE_WU_XIE
                and state['level'] == 4
                and state['level4_objectives']['sky_lever']
                and self._near(player, state['astrolabe'], 80)
                and isinstance(tiles, list) and len(tiles) == 4
                and all(isinstance(tile, int) and tile % 4 == 0 for tile in tiles)
            )
            if valid:
                state['astrolabe_puzzle']['tiles'] = [0, 0, 0, 0]
                state['level4_objectives']['astrolabe'] = True
                state['door_open'] = True
                state['notice'] = f"{player['username']} 让四象归位，悬宫出口已经打开"
            else:
                await self.send(text_data=json.dumps({'type': 'puzzle_error', 'message': '四象方位仍未归正'}))
            await self.broadcast_game_state()
        elif action == 'next_level':
            state = IRON_GAME_STATES.get(self.room_id)
            if state and state['completed'] and state['level'] == 1:
                self._load_second_level(state)
                await self.broadcast_game_state(full=True)
            elif state and state['completed'] and state['level'] == 2:
                self._load_third_level(state)
                await self.broadcast_game_state(full=True)
            elif state and state['completed'] and state['level'] == 3:
                self._load_fourth_level(state)
                await self.broadcast_game_state(full=True)
        elif action == 'attack':
            state = IRON_GAME_STATES.get(self.room_id)
            player = state and state['players'].get(str(self.scope['user'].id))
            if not player or state['level'] != 3 or player['attack_cooldown'] > 0:
                return
            self._perform_attack(state, player)
            await self.broadcast_game_state()

    async def broadcast_room_info(self):
        """广播房间信息"""
        # 调用服务层获取数据
        players = await self.get_players()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'room_info', 'players': players}
        )

    async def room_info(self, event):
        """处理广播：发送房间信息给前端"""
        await self.send(text_data=json.dumps({
            'type': 'room_info',
            'players': event['players']
        }))

    async def game_start(self, event):
        """处理广播：游戏开始"""
        await self.send(text_data=json.dumps({
            'type': 'game_start',
            'room_id': event['room_id']
        }))

    async def level_select(self, event):
        await self.send(text_data=json.dumps({
            'type': 'level_select',
            'unlocked_level': event['unlocked_level'],
            'is_host': self.scope['user'].id == await self.get_host_id(),
        }))

    async def game_state(self, event):
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'state': event['state'],
            'full': event.get('full', False),
            'my_id': str(self.scope['user'].id),
        }))

    async def broadcast_game_state(self, full=False):
        state = IRON_GAME_STATES.get(self.room_id)
        if state:
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'game_state', 'state': self._state_payload(state, full), 'full': full},
            )

    async def send_game_state(self):
        state = IRON_GAME_STATES.get(self.room_id)
        if state:
            await self.send(text_data=json.dumps({
                'type': 'game_state', 'state': self._state_payload(state, True),
                'full': True,
                'my_id': str(self.scope['user'].id),
            }))

    @staticmethod
    def _state_payload(state, full=False):
        if full:
            # 伏击坐标属于服务端秘密，完整初始化包也不应把它们提前交给浏览器。
            return {
                key: value for key, value in state.items()
                if key not in ('ambushes', 'zombie_serial')
            }
        player_fields = ('id', 'username', 'role', 'x', 'y', 'facing', 'grounded', 'hp', 'attack_flash')
        payload = {
            'level': state['level'],
            'players': {
                player_id: {key: player[key] for key in player_fields if key in player}
                for player_id, player in state['players'].items()
            },
            'door_open': state['door_open'],
            'completed': state['completed'],
            'notice': state['notice'],
        }
        for key in (
            'objectives', 'crate', 'rope', 'zombies', 'explosions', 'moving_platforms',
            'level4_objectives', 'counterweight', 'sky_lever', 'astrolabe',
            'phase_platforms', 'swing_ropes',
        ):
            if key in state:
                payload[key] = state[key]
        return payload

    async def ensure_game_state(self, reset=False):
        if self.room_id in IRON_GAME_STATES and not reset:
            return
        players = await self.get_players()
        IRON_GAME_STATES[self.room_id] = {
            'width': 1200,
            'height': 650,
            'level': 1,
            'paused': False,
            'progress_saved': False,
            'platforms': FOREST_PLATFORMS,
            'hazards': FOREST_HAZARDS,
            'door': {'x': 1125, 'y': 510, 'w': 55, 'h': 90},
            'crate': {'x': 650, 'y': 552, 'w': 48, 'h': 48},
            'plate': {'x': 790, 'y': 592, 'w': 90, 'h': 8},
            'console': {'x': 565, 'y': 382, 'w': 42, 'h': 48},
            'lever': {'x': 1100, 'y': 225, 'w': 24, 'h': 55},
            'objectives': {'plate': False, 'console': False, 'lever': False},
            'door_open': False,
            'completed': False,
            'notice': '三人分头寻找各自能够操作的机关',
            'puzzle': {'tiles': [1, 3, 2, 1]},
            'players': {
                str(player['user_id']): {
                    'id': str(player['user_id']),
                    'username': player['user__username'],
                    'role': player['role'],
                    'x': ROLE_STARTS[player['role']]['x'],
                    'y': ROLE_STARTS[player['role']]['y'],
                    'facing': 'right',
                    'vx': 0,
                    'vy': 0,
                    'grounded': False,
                    'jumps_remaining': 2 if player['role'] == GamePlayer.ROLE_XIAOGE else 1,
                    'input': {'left': False, 'right': False},
                }
                for player in players
            },
        }

    def ensure_game_loop(self, restart=False):
        task = IRON_GAME_LOOPS.get(self.room_id)
        if restart and task and not task.done():
            task.cancel()
        if restart or not task or task.done():
            IRON_GAME_LOOPS[self.room_id] = asyncio.create_task(self.iron_game_loop())

    async def iron_game_loop(self):
        tick = 0
        try:
            while self.room_id in IRON_GAME_STATES:
                state = IRON_GAME_STATES[self.room_id]
                if state.get('paused'):
                    await asyncio.sleep(.1)
                    continue
                if state['level'] in (3, 4):
                    self._update_moving_platforms(state)
                if state['level'] == 4:
                    self._update_swing_ropes(state)
                for player in state['players'].values():
                    if state['level'] == 2 and state['rope']['pulling'] and player['role'] == GamePlayer.ROLE_PANGZI:
                        progress = min(1, state['rope']['progress'] + .018)
                        state['rope']['progress'] = progress
                        player['x'] = state['rope']['start_x'] + (850 - state['rope']['start_x']) * progress
                        player['y'] = state['rope']['start_y'] + (330 - state['rope']['start_y']) * progress - 115 * (4 * progress * (1 - progress))
                        player['vx'] = player['vy'] = 0
                        player['grounded'] = False
                        if progress >= 1:
                            state['rope']['pulling'] = False
                            state['rope']['completed'] = True
                            player['y'] = 342
                            state['notice'] = '胖子安全落地，铁三角可以继续前进了'
                        continue
                    if state['level'] == 4 and player.get('attached_rope'):
                        player['attack_flash'] = 0
                        continue
                    player['attack_cooldown'] = max(0, player.get('attack_cooldown', 0) - 1)
                    player['attack_flash'] = max(0, player.get('attack_flash', 0) - 1)
                    speed = 9 if player['role'] == GamePlayer.ROLE_XIAOGE else (4 if player['role'] == GamePlayer.ROLE_PANGZI else 7)
                    if player.get('release_momentum_ticks', 0) > 0:
                        player['release_momentum_ticks'] -= 1
                        player['vx'] *= .94
                    else:
                        player['vx'] = (-speed if player['input']['left'] else 0) + (speed if player['input']['right'] else 0)
                    if player['vx']:
                        player['facing'] = 'left' if player['vx'] < 0 else 'right'
                    old_bottom = player['y'] + 48
                    old_x = player['x']
                    player['x'] = max(0, min(state['width'] - 32, player['x'] + player['vx']))
                    player['vy'] = min(15, player['vy'] + .8)
                    player['y'] += player['vy']
                    player['grounded'] = False
                    new_bottom = player['y'] + 48
                    if player['vy'] >= 0:
                        collision_platforms = state['platforms'] + [
                            platform for platform in state.get('moving_platforms', [])
                            if not platform.get('requires')
                            or state.get('level4_objectives', {}).get(platform['requires'])
                        ]
                        if state.get('level4_objectives', {}).get('sky_lever'):
                            collision_platforms += state.get('phase_platforms', [])
                        for platform in collision_platforms:
                            overlaps_x = player['x'] + 28 > platform['x'] and player['x'] + 4 < platform['x'] + platform['w']
                            if overlaps_x and old_bottom <= platform['y'] and new_bottom >= platform['y']:
                                player['y'] = platform['y'] - 48
                                player['vy'] = 0
                                player['grounded'] = True
                                player['jumps_remaining'] = 2 if player['role'] == GamePlayer.ROLE_XIAOGE else 1
                                break
                    if self._touches_hazard(player, state['hazards']) or player['y'] > state['height']:
                        spawn = ROLE_STARTS[player['role']]
                        player['x'], player['y'], player['vx'], player['vy'] = spawn['x'], spawn['y'], 0, 0
                        player.pop('release_momentum_ticks', None)
                    if state['level'] == 1 and player['role'] == GamePlayer.ROLE_PANGZI and abs(player['y'] + 48 - state['crate']['y'] - state['crate']['h']) < 16:
                        crate = state['crate']
                        touching = player['x'] + 32 > crate['x'] and player['x'] < crate['x'] + crate['w']
                        if touching and player['vx']:
                            # 踏板右侧有石挡，箱子推上去后不会越过机关导致无法复原。
                            crate['x'] = max(520, min(832, crate['x'] + player['vx']))
                            player['x'] = crate['x'] - 32 if player['vx'] > 0 else crate['x'] + crate['w']
                if state['level'] == 1:
                    plate = state['plate']
                    crate = state['crate']
                    state['objectives']['plate'] = crate['x'] + crate['w'] > plate['x'] and crate['x'] < plate['x'] + plate['w']
                    state['door_open'] = all(state['objectives'].values())
                elif state['level'] == 3:
                    self._update_zombies(state)
                    wu_xie = next((p for p in state['players'].values() if p['role'] == GamePlayer.ROLE_WU_XIE), None)
                    if wu_xie:
                        for ambush in state['ambushes']:
                            if wu_xie['x'] > ambush['x'] and not ambush['triggered']:
                                ambush['triggered'] = True
                                for _ in range(ambush['count']):
                                    state['zombie_serial'] += 1
                                    state['zombies'].append({
                                        'id': f"z{state['zombie_serial']}",
                                        # 吴邪踩中不可见区域后，粽子才从他身边突然钻出。
                                        'x': max(30, min(1110, wu_xie['x'] + random.choice((-1, 1)) * random.randint(45, 115))),
                                        'y': 548, 'hp': 100, 'alive': True,
                                        'attack_cooldown': 0, 'rise': random.randint(6, 10),
                                    })
                                state['notice'] = '棺木突然炸裂，黑暗中传来沉重的脚步声！'
                    all_ambushes = all(ambush['triggered'] for ambush in state['ambushes'])
                    state['door_open'] = all_ambushes and all(not zombie['alive'] for zombie in state['zombies'])
                    if state['door_open'] and not state['completed']:
                        state['notice'] = '粽子已经清除，墓道尽头的门开了'
                elif state['level'] == 4:
                    state['door_open'] = all(state['level4_objectives'].values())
                if state['door_open']:
                    door = state['door']
                    at_exit = [
                        p for p in state['players'].values()
                        if p['x'] + 32 > door['x'] - 35 and p['x'] < door['x'] + door['w']
                    ]
                    if len(at_exit) == 3:
                        state['completed'] = True
                        state['notice'] = '铁三角全员抵达出口！'
                if state['completed'] and not state.get('progress_saved'):
                    state['progress_saved'] = True
                    await self.unlock_room_level(min(4, state['level'] + 1))
                # 动态包已精简，恢复 20Hz 广播让移动与战斗响应更及时。
                tick += 1
                await self.broadcast_game_state()
                await asyncio.sleep(.05)
        except asyncio.CancelledError:
            return

    @staticmethod
    def _touches_hazard(player, hazards):
        return any(
            player['x'] + 28 > hazard['x'] and player['x'] + 4 < hazard['x'] + hazard['w']
            and player['y'] + 48 > hazard['y'] and player['y'] < hazard['y'] + hazard['h']
            for hazard in hazards
        )

    @staticmethod
    def _load_second_level(state):
        state.update({
            'level': 2,
            'platforms': SECOND_LEVEL_PLATFORMS,
            'hazards': SECOND_LEVEL_HAZARDS,
            'door': {'x': 1125, 'y': 510, 'w': 55, 'h': 90},
            'door_open': True,
            'completed': False,
            'paused': False,
            'progress_saved': False,
            'notice': '第二关：蛇沼石廊。越过断崖，在另一端重新集合。',
            'rope': {
                'anchor': {'x': 850, 'y': 335, 'w': 24, 'h': 55},
                'deployed': False,
                'pulling': False,
                'completed': False,
                'progress': 0,
            },
        })
        for player in state['players'].values():
            spawn = ROLE_STARTS[player['role']]
            player.update({
                'x': spawn['x'], 'y': spawn['y'], 'vx': 0, 'vy': 0,
                'grounded': False,
                'jumps_remaining': 2 if player['role'] == GamePlayer.ROLE_XIAOGE else 1,
                'input': {'left': False, 'right': False},
            })

    @staticmethod
    def _load_third_level(state):
        # 第二关绳索只属于蛇沼石廊，绝不能泄漏到后续关卡。
        state.pop('rope', None)
        state.update({
            'level': 3,
            'platforms': THIRD_LEVEL_PLATFORMS,
            'hazards': [],
            'door': {'x': 1125, 'y': 510, 'w': 55, 'h': 90},
            'door_open': False,
            'completed': False,
            'paused': False,
            'progress_saved': False,
            'ambushes': [
                {'x': 275, 'count': 3, 'triggered': False},
                {'x': 650, 'count': 3, 'triggered': False},
                {'x': 870, 'count': 2, 'triggered': False},
            ],
            'zombie_serial': 0,
            'zombies': [],
            'explosions': [],
            'moving_platforms': [
                {'x': 365, 'y': 555, 'w': 72, 'h': 18, 'min_y': 445, 'max_y': 555, 'dy': -1.8},
                {'x': 715, 'y': 350, 'w': 105, 'h': 18, 'min_x': 610, 'max_x': 820, 'dx': 2.1},
                {'x': 1010, 'y': 555, 'w': 72, 'h': 18, 'min_y': 440, 'max_y': 555, 'dy': -1.6},
            ],
            'notice': '',
        })
        for player in state['players'].values():
            spawn = ROLE_STARTS[player['role']]
            player.update({
                'x': spawn['x'], 'y': spawn['y'], 'vx': 0, 'vy': 0,
                'hp': 100, 'attack_cooldown': 0, 'attack_flash': 0,
                'grounded': False,
                'jumps_remaining': 2 if player['role'] == GamePlayer.ROLE_XIAOGE else 1,
                'input': {'left': False, 'right': False},
            })

    @staticmethod
    def _load_fourth_level(state):
        # 每一关只保留自己的机关，避免绳索或战斗对象跨关残留。
        for key in ('rope', 'ambushes', 'zombie_serial', 'zombies', 'explosions', 'pendulums'):
            state.pop(key, None)
        state.update({
            'level': 4,
            'platforms': FOURTH_LEVEL_PLATFORMS,
            'hazards': FOURTH_LEVEL_HAZARDS,
            'door': {'x': 1125, 'y': 510, 'w': 55, 'h': 90},
            'door_open': False,
            'completed': False,
            'paused': False,
            'progress_saved': False,
            'level4_objectives': {
                'counterweight': False,
                'sky_lever': False,
                'astrolabe': False,
            },
            'counterweight': {'x': 330, 'y': 477, 'w': 42, 'h': 58},
            'sky_lever': {'x': 730, 'y': 395, 'w': 28, 'h': 60},
            'astrolabe': {'x': 835, 'y': 300, 'w': 52, 'h': 60},
            'astrolabe_puzzle': {'tiles': [2, 3, 1, 2]},
            'moving_platforms': [
                {'x': 195, 'y': 560, 'w': 78, 'h': 18, 'min_x': 190, 'max_x': 295, 'dx': 1.8},
                {
                    'x': 440, 'y': 555, 'w': 72, 'h': 18,
                    'min_y': 430, 'max_y': 555, 'dy': -1.8,
                    'requires': 'counterweight',
                },
                {
                    'x': 925, 'y': 445, 'w': 82, 'h': 18,
                    'min_x': 915, 'max_x': 1065, 'dx': 2.0,
                    'requires': 'sky_lever',
                },
            ],
            'phase_platforms': [
                {'x': 780, 'y': 415, 'w': 70, 'h': 16},
                {'x': 930, 'y': 405, 'w': 70, 'h': 16},
            ],
            'swing_ropes': [
                {
                    'id': 'swing-1', 'anchor_x': 480, 'anchor_y': 35, 'length': 450,
                    'angle': -.16, 'angular_velocity': 0, 'idle_direction': 1,
                    'x': 0, 'y': 0, 'rider': None,
                },
                {
                    'id': 'swing-2', 'anchor_x': 900, 'anchor_y': 35, 'length': 450,
                    'angle': -.16, 'angular_velocity': 0, 'idle_direction': -1,
                    'x': 0, 'y': 0, 'rider': None,
                },
            ],
            'notice': '悬宫没有直路，三人必须分别找到属于自己的机关',
        })
        for rope in state['swing_ropes']:
            IronTriangleConsumer._position_swing_rope(rope)
        for player in state['players'].values():
            for key in ('hp', 'attack_cooldown', 'attack_flash'):
                player.pop(key, None)
            player.pop('attached_rope', None)
            player.pop('release_momentum_ticks', None)
            spawn = ROLE_STARTS[player['role']]
            player.update({
                'x': spawn['x'], 'y': spawn['y'], 'vx': 0, 'vy': 0,
                'grounded': False,
                'jumps_remaining': 2 if player['role'] == GamePlayer.ROLE_XIAOGE else 1,
                'input': {'left': False, 'right': False},
            })

    @staticmethod
    def _perform_attack(state, player):
        direction = -1 if player['facing'] == 'left' else 1
        living = [zombie for zombie in state['zombies'] if zombie['alive']]
        player['attack_flash'] = 5
        if player['role'] == GamePlayer.ROLE_PANGZI:
            player['attack_cooldown'] = 22
            candidates = [
                zombie for zombie in living
                if 0 <= (zombie['x'] - player['x']) * direction <= 430
            ]
            if candidates:
                target = min(candidates, key=lambda zombie: abs(zombie['x'] - player['x']))
                state['explosions'].append({'x': target['x'], 'y': target['y'] + 20, 'ttl': 8})
                for zombie in living:
                    if abs(zombie['x'] - target['x']) <= 120:
                        zombie['hp'] = max(0, zombie['hp'] - 45)
                        zombie['alive'] = zombie['hp'] > 0
        else:
            is_xiaoge = player['role'] == GamePlayer.ROLE_XIAOGE
            player['attack_cooldown'] = 5 if is_xiaoge else 9
            attack_range = 95 if is_xiaoge else 72
            damage = 42 if is_xiaoge else 28
            for zombie in living:
                if abs(zombie['x'] - player['x']) <= attack_range and abs(zombie['y'] - player['y']) <= 70:
                    zombie['hp'] = max(0, zombie['hp'] - damage)
                    zombie['alive'] = zombie['hp'] > 0

    @staticmethod
    def _update_zombies(state):
        for explosion in state['explosions']:
            explosion['ttl'] -= 1
        state['explosions'] = [explosion for explosion in state['explosions'] if explosion['ttl'] > 0]
        if not any(ambush['triggered'] for ambush in state['ambushes']):
            return
        players = list(state['players'].values())
        for zombie in state['zombies']:
            if not zombie['alive']:
                continue
            zombie['rise'] = max(0, zombie.get('rise', 0) - 1)
            zombie['attack_cooldown'] = max(0, zombie['attack_cooldown'] - 1)
            target = min(players, key=lambda player: abs(player['x'] - zombie['x']))
            distance = target['x'] - zombie['x']
            if abs(distance) > 34:
                zombie['x'] += 2.25 if distance > 0 else -2.25
            elif zombie['attack_cooldown'] == 0:
                target['hp'] = max(0, target.get('hp', 100) - 8)
                zombie['attack_cooldown'] = 18
                if target['hp'] == 0:
                    spawn = ROLE_STARTS[target['role']]
                    target.update({'x': spawn['x'], 'y': spawn['y'], 'hp': 100, 'vy': 0})

    @staticmethod
    def _update_moving_platforms(state):
        for platform in state.get('moving_platforms', []):
            requirement = platform.get('requires')
            if requirement and not state.get('level4_objectives', {}).get(requirement):
                continue
            old_x, old_y = platform['x'], platform['y']
            if 'dy' in platform:
                platform['y'] += platform['dy']
                if platform['y'] <= platform['min_y'] or platform['y'] >= platform['max_y']:
                    platform['dy'] *= -1
                    platform['y'] = max(platform['min_y'], min(platform['max_y'], platform['y']))
            if 'dx' in platform:
                platform['x'] += platform['dx']
                if platform['x'] <= platform['min_x'] or platform['x'] >= platform['max_x']:
                    platform['dx'] *= -1
                    platform['x'] = max(platform['min_x'], min(platform['max_x'], platform['x']))
            move_x, move_y = platform['x'] - old_x, platform['y'] - old_y
            if not move_x and not move_y:
                continue
            # 站在平台上的角色随平台一起移动，避免升降台从脚下滑走造成卡顿。
            for player in state.get('players', {}).values():
                was_on_platform = (
                    player.get('grounded')
                    and abs(player['y'] + 48 - old_y) <= 5
                    and player['x'] + 28 > old_x
                    and player['x'] + 4 < old_x + platform['w']
                )
                if was_on_platform:
                    player['x'] = max(0, min(state['width'] - 32, player['x'] + move_x))
                    player['y'] += move_y

    @staticmethod
    def _position_swing_rope(rope):
        rope['x'] = rope['anchor_x'] + math.sin(rope['angle']) * rope['length']
        rope['y'] = rope['anchor_y'] + math.cos(rope['angle']) * rope['length']

    @staticmethod
    def _update_swing_ropes(state):
        players = state.get('players', {})
        for rope in state.get('swing_ropes', []):
            rider = players.get(rope.get('rider'))
            if rope.get('rider') and not rider:
                rope['rider'] = None
            if rider:
                if rider['input']['left']:
                    rope['angular_velocity'] -= .0012
                if rider['input']['right']:
                    rope['angular_velocity'] += .0012
            elif abs(rope['angle']) < .025 and abs(rope['angular_velocity']) < .0025:
                # 无人操作时也维持轻微摆动，不让绳索像一根僵硬的直线停住。
                rope['angular_velocity'] = .007 * rope.get('idle_direction', 1)
                rope['idle_direction'] = -rope.get('idle_direction', 1)
            rope['angular_velocity'] += -.0027 * math.sin(rope['angle'])
            rope['angular_velocity'] *= .997
            rope['angular_velocity'] = max(-.048, min(.048, rope['angular_velocity']))
            rope['angle'] += rope['angular_velocity']
            IronTriangleConsumer._position_swing_rope(rope)
            if rider:
                rider['x'] = rope['x'] - 16
                rider['y'] = rope['y'] - 24
                rider['vx'] = rider['vy'] = 0
                rider['grounded'] = False
                if abs(rope['angular_velocity']) > .004:
                    rider['facing'] = 'right' if rope['angular_velocity'] > 0 else 'left'

    @staticmethod
    def _release_swing_rope(state, player, rope):
        tangent_x = rope['angular_velocity'] * rope['length'] * math.cos(rope['angle'])
        tangent_y = -rope['angular_velocity'] * rope['length'] * math.sin(rope['angle'])
        rope['rider'] = None
        player.pop('attached_rope', None)
        player['vx'] = max(-15, min(15, tangent_x))
        player['vy'] = max(-16, min(13, tangent_y))
        player['release_momentum_ticks'] = 12
        player['grounded'] = False

    @staticmethod
    def _detach_level_two_rope(state, player):
        state['rope']['pulling'] = False
        state['rope']['deployed'] = False
        player['vy'] = 0

    @staticmethod
    def _near(player, target, distance=70):
        player_x, player_y = player['x'] + 16, player['y'] + 24
        target_x = target['x'] + target.get('w', 0) / 2
        target_y = target['y'] + target.get('h', 0) / 2
        return abs(player_x - target_x) <= distance and abs(player_y - target_y) <= distance

    async def user_joined(self, event):
        message = event['message']
        
        # 将消息发送给 WebSocket 连接的客户端（前端）
        await self.send(text_data=json.dumps({
            'type': 'notification', # 前端根据 type 判断类型
            'data': message
        }))

    @database_sync_to_async
    def is_room_player(self, user_id):
        return GamePlayer.objects.filter(room__room_id=self.room_id, user_id=user_id).exists()

    @database_sync_to_async
    def get_players(self):
        return list(
            GamePlayer.objects.filter(room__room_id=self.room_id)
            .select_related('user')
            .values('user_id', 'user__username', 'role')
        )

    @database_sync_to_async
    def get_player_role(self, user_id):
        return GamePlayer.objects.filter(
            room__room_id=self.room_id, user_id=user_id
        ).values_list('role', flat=True).first()

    @database_sync_to_async
    def get_room_status(self):
        return GameRoom.objects.filter(room_id=self.room_id).values_list('status', flat=True).first()

    @database_sync_to_async
    def get_host_id(self):
        return GameRoom.objects.filter(room_id=self.room_id).values_list('host_id', flat=True).first()

    @database_sync_to_async
    def is_host(self):
        return GameRoom.objects.filter(room_id=self.room_id, host_id=self.scope['user'].id).exists()

    @database_sync_to_async
    def get_room_unlocked_level(self):
        user_ids = list(GamePlayer.objects.filter(room__room_id=self.room_id).values_list('user_id', flat=True))
        if not user_ids:
            return 1
        levels = []
        for user_id in user_ids:
            progress, _ = ForestProgress.objects.get_or_create(user_id=user_id)
            levels.append(progress.highest_unlocked_level)
        return min(levels)

    @database_sync_to_async
    def unlock_room_level(self, level):
        user_ids = GamePlayer.objects.filter(room__room_id=self.room_id).values_list('user_id', flat=True)
        for user_id in user_ids:
            progress, _ = ForestProgress.objects.get_or_create(user_id=user_id)
            if progress.highest_unlocked_level < level:
                progress.highest_unlocked_level = level
                progress.save(update_fields=['highest_unlocked_level'])

    @database_sync_to_async
    def can_start_game(self):
        try:
            room = GameRoom.objects.get(room_id=self.room_id)
        except GameRoom.DoesNotExist:
            return False
        roles = set(room.players.values_list('role', flat=True))
        ready = roles == {
            GamePlayer.ROLE_WU_XIE,
            GamePlayer.ROLE_XIAOGE,
            GamePlayer.ROLE_PANGZI,
        }
        if room.host_id == self.scope['user'].id and ready:
            room.status = 'playing'
            room.save(update_fields=['status'])
            return True
        return False
