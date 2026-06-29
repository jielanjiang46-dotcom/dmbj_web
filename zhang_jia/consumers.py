# consumers.py

import json
import random
import asyncio
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

        # 5. 立即发送一次当前状态给新进来的玩家（防止他进来是一片黑）
        await self.send(text_data=json.dumps({
            'type': 'update_game',
            'snakes': room_data['snakes'],
            'foods': room_data['foods'],
            'my_id': str(self.user.id) # 【关键修复 2】告诉前端哪条蛇是它自己的
        }))

        # 6. 如果这条蛇还不存在，立刻创建它
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
                await asyncio.sleep(0.3) 
                
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