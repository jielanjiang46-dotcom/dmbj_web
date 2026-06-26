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
                'players': {}, # 记录玩家ID和角色的映射 {'channel_name': 'snake'}
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
            
            room_data['snakes'] = [s for s in room_data['snakes'] if s['id'] != self.channel_name]

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('type')

        # 1. 玩家加入房间
        if action == 'join_game':
            role = data.get('role', 'snake')
            player_id = self.channel_name 
            
            room_data = GAME_ROOMS[self.room_name]
            
            # 记录玩家角色
            room_data['players'][player_id] = role
            
            # 如果是蛇，初始化位置
            if role == 'snake':
                new_snake = {
                    'id': player_id,
                    'body': [{'x': random.randint(5, 25), 'y': random.randint(5, 25)}],
                    'dx': 1, 'dy': 0,
                    'alive': True
                }
                room_data['snakes'].append(new_snake)
            
            # 立即发送一次当前状态给新进来的玩家
            await self.send_state()

        # 2. 【核心修改】检查是否可以开始游戏
        elif action == 'check_start':
            room_data = GAME_ROOMS[self.room_name]
            roles = list(room_data['players'].values())
            
            # 判断房间里是否同时存在 'snake' 和 'food'
            can_start = 'snake' in roles and 'food' in roles
            
            # 将检查结果发回给请求的客户端
            await self.send(text_data=json.dumps({
                'type': 'start_check_result',
                'can_start': can_start,
                'message': '可以开始！' if can_start else '还需要一个信物或蛇才能开始！'
            }))

        # 3. 玩家移动
        elif action == 'move':
            direction = data.get('direction')
            room_data = GAME_ROOMS[self.room_name]
            
            # 找到当前玩家并更新方向
            for snake in room_data['snakes']:
                if snake['id'] == self.channel_name and snake['alive']:
                    # 防止直接掉头
                    if direction == 'up' and snake['dy'] != 1:
                        snake['dx'], snake['dy'] = 0, -1
                    elif direction == 'down' and snake['dy'] != -1:
                        snake['dx'], snake['dy'] = 0, 1
                    elif direction == 'left' and snake['dx'] != 1:
                        snake['dx'], snake['dy'] = -1, 0
                    elif direction == 'right' and snake['dx'] != -1:
                        snake['dx'], snake['dy'] = 1, 0

    async def game_loop(self, room_name):
        """
        这是服务器的核心心跳：每 0.15 秒执行一次物理计算
        """
        while True:
            await asyncio.sleep(0.15) # 游戏速度控制
            
            if room_name not in GAME_ROOMS:
                break
                
            room_data = GAME_ROOMS[room_name]
            grid_size = 30 # 对应前端的 tileCount
            
            # 1. 移动所有蛇
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
                for i, food in enumerate(room_data['foods']):
                    if new_head['x'] == food['x'] and new_head['y'] == food['y']:
                        room_data['foods'].pop(i)
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

            # 5. 广播最新状态给房间内所有人
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'broadcast_state',
                    'snakes': room_data['snakes'],
                    'foods': room_data['foods']
                }
            )

    async def broadcast_state(self, event):
        """接收 loop 发来的指令，转发给 WebSocket 客户端"""
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'snakes': event['snakes'],
            'foods': event['foods'],
            'my_id': self.channel_name
        }))

    async def send_state(self):
        """辅助方法：单独给某个人发一次状态"""
        room_data = GAME_ROOMS[self.room_name]
        await self.send(text_data=json.dumps({
            'type': 'game_state',
            'snakes': room_data['snakes'],
            'foods': room_data['foods'],
            'my_id': self.channel_name
        }))