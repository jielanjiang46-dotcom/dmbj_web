import json
import random
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer

# 全局变量：存储所有房间的游戏状态
GAME_ROOMS = {}

class SnakeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'snake_{self.room_name}'
        
        # 加入频道组
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

        # 初始化或加入房间逻辑
        if self.room_name not in GAME_ROOMS:
            GAME_ROOMS[self.room_name] = {
                'snakes': [], 
                'foods': [],
                'players': {}, 
                'loop_task': None
            }
            print(f"🆕 创建新房间: {self.room_name}")
        
        # 启动该房间的游戏循环（如果还没启动）
        room_data = GAME_ROOMS[self.room_name]
        if room_data['loop_task'] is None or room_data['loop_task'].done():
            room_data['loop_task'] = asyncio.create_task(self.game_loop(self.room_name))
            print(f"🚀 启动房间 {self.room_name} 的游戏循环")

    async def disconnect(self, close_code):
        # 离开频道组
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # 清理逻辑：从玩家列表和蛇列表中移除
        if self.room_name in GAME_ROOMS:
            room_data = GAME_ROOMS[self.room_name]
            if self.channel_name in room_data['players']:
                del room_data['players'][self.channel_name]
            
            # 移除对应的蛇
            room_data['snakes'] = [s for s in room_data['snakes'] if s['id'] != self.channel_name]
            
            # 【修复点】如果房间里没人了，清理掉房间数据，防止内存泄漏
            if not room_data['players']:
                if room_data['loop_task'] and not room_data['loop_task'].done():
                    room_data['loop_task'].cancel()
                del GAME_ROOMS[self.room_name]
                print(f"🧹 房间 {self.room_name} 已清空并销毁")

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('type')
        room_data = GAME_ROOMS.get(self.room_name)

        if not room_data: 
            return

        # 1. 玩家加入/设置身份
        if action == 'set_role':
            username = data.get('username', 'Guest') 
            player_id = self.channel_name
            
            # 记录玩家信息
            room_data['players'][player_id] = {
                'username': username,
                'score': 0
            }
            
            # 如果这条蛇还不存在，就创建它
            existing = [s for s in room_data['snakes'] if s['id'] == player_id]
            if not existing:
                new_snake = {
                    'id': player_id,
                    'body': [{'x': random.randint(5, 25), 'y': random.randint(5, 25)}],
                    'dx': 1, 'dy': 0,
                    'alive': True
                }
                room_data['snakes'].append(new_snake)
            
            print(f"🐍 玩家 {username} 已加入战场")

        # 2. 玩家移动
        elif action == 'move':
            direction = data.get('direction')
            for snake in room_data['snakes']:
                # 只有活着的、且ID匹配的蛇才能移动
                if snake['id'] == self.channel_name and snake['alive']:
                    if direction == 'up' and snake['dy'] != 1:
                        snake['dx'], snake['dy'] = 0, -1
                    elif direction == 'down' and snake['dy'] != -1:
                        snake['dx'], snake['dy'] = 0, 1
                    elif direction == 'left' and snake['dx'] != 1:
                        snake['dx'], snake['dy'] = -1, 0
                    elif direction == 'right' and snake['dx'] != -1:
                        snake['dx'], snake['dy'] = 1, 0

    async def broadcast_state(self, event):
        """
        【新增】处理来自 group_send 的广播消息
        将后端计算好的状态发送给前端 WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'update_game',  # 前端通过这个 type 识别是游戏画面更新
            'snakes': event['snakes'],
            'foods': event['foods']
        }))

    async def end_game(self, room_name):
        """
        处理游戏结束逻辑
        """
        print(f"🏁 房间 {room_name} 游戏结束")
        
        # 1. 通知所有玩家游戏结束了
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_over_message', # 这里定义一个新的消息类型
                'message': 'Game Over! All snakes are dead.'
            }
        )

    async def game_over_message(self, event):
        """
        接收 game_over_message 并发送给前端
        """
        await self.send(text_data=json.dumps({
            'type': 'game_over', # 前端收到这个 type 就可以弹出“游戏结束”界面
            'message': event['message']
        }))

    async def game_loop(self, room_name):
        while True:
            await asyncio.sleep(0.15) 
            
            # 检查房间是否还存在
            if room_name not in GAME_ROOMS:
                break
                
            room_data = GAME_ROOMS[room_name]
            grid_size = 30 

            # 1. 移动所有蛇
            # 【优化】先检查有没有蛇，避免空列表操作
            if room_data['snakes']:
                for snake in room_data['snakes']:
                    if not snake['alive']: continue
                    
                    head = snake['body'][0]
                    new_head = {'x': head['x'] + snake['dx'], 'y': head['y'] + snake['dy']}
                    
                    # 2. 碰撞检测 (撞墙)
                    if new_head['x'] < 0 or new_head['x'] >= grid_size or \
                       new_head['y'] < 0 or new_head['y'] >= grid_size:
                        snake['alive'] = False
                        continue
                        
                    snake['body'].insert(0, new_head)
                    
                    # 3. 吃食物检测
                    ate_food = False
                    # 使用倒序遍历或者 copy 列表来安全删除，或者直接判断索引
                    # 这里为了简单保持原逻辑，但注意 pop(i) 在循环中可能跳过元素，
                    # 不过因为吃到就 break，所以没问题。
                    for i, food in enumerate(room_data['foods']):
                        if new_head['x'] == food['x'] and new_head['y'] == food['y']:
                            room_data['foods'].pop(i)
                            ate_food = True
                            
                            # 👑 吃食物加分
                            player_id = snake['id']
                            if player_id in room_data['players']:
                                room_data['players'][player_id]['score'] += 1
                            break
                    
                    if not ate_food:
                        snake['body'].pop()
            
            # 4. 补充食物
            while len(room_data['foods']) < 5:
                room_data['foods'].append({
                    'x': random.randint(0, grid_size - 1),
                    'y': random.randint(0, grid_size - 1)
                })

            # 🏁 判断游戏是否结束（所有蛇都死了）
            alive_snakes = [s for s in room_data['snakes'] if s['alive']]
            if len(alive_snakes) == 0 and len(room_data['snakes']) > 0:
                await self.end_game(room_name)
                break  # 游戏结束，跳出循环

            # 5. 广播最新状态
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'broadcast_state',
                    'snakes': room_data['snakes'],
                    'foods': room_data['foods']
                }
            )