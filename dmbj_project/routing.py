from django.urls import re_path
from zhang_jia.consumers import SnakeConsumer
from zhang_jia.consumers import IronTriangleConsumer

# 定义 WebSocket 的路由列表
websocket_urlpatterns = [
    # 修改重点：在 $ 符号前加上 /? 
    # /? 表示前面的斜杠是“可选的”（出现0次或1次）
    # 这样无论前端发的是 .../2053 还是 .../2053/ 都能匹配上
    re_path(r'^ws/snake/(?P<room_name>\w+)/?$', SnakeConsumer.as_asgi()),
    re_path(r'^ws/iron_triangle/(?P<room_id>\w+)/?$', IronTriangleConsumer.as_asgi()),
]
