# services.py
import threading

# 使用全局字典模拟存储，threading.Lock 保证多线程/多协程下的数据安全
GAME_ROOMS = {}
_lock = threading.Lock()


def get_room_players(room_id: str) -> list:
    """
    获取指定房间的所有玩家列表
    """
    with _lock:
        # 如果房间不存在，返回空列表，避免报错
        return GAME_ROOMS.get(room_id, [])


def add_player_to_room(room_id: str, player_data: dict) -> None:
    """
    将玩家加入指定房间
    player_data 示例: {'username': 'wuxie', 'channel_name': 'xxx'}
    """
    with _lock:
        if room_id not in GAME_ROOMS:
            GAME_ROOMS[room_id] = []
        
        # 简单的去重逻辑：如果玩家已经在房间里，就不重复添加
        exists = any(p.get('username') == player_data.get('username') for p in GAME_ROOMS[room_id])
        if not exists:
            GAME_ROOMS[room_id].append(player_data)


def remove_player_from_room(room_id: str, username: str) -> None:
    """
    将玩家从指定房间移除
    """
    with _lock:
        if room_id in GAME_ROOMS:
            # 过滤掉要移除的玩家
            GAME_ROOMS[room_id] = [
                p for p in GAME_ROOMS[room_id] 
                if p.get('username') != username
            ]
            # 如果房间空了，顺便把房间也删掉，防止内存泄漏
            if not GAME_ROOMS[room_id]:
                del GAME_ROOMS[room_id]