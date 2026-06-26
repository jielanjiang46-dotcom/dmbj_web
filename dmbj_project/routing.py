from django.urls import re_path
from zhang_jia.consumers import SnakeConsumer

# 定义 WebSocket 的路由列表
websocket_urlpatterns = [
    # 这里的正则表达式必须和前端的 js 代码完全匹配
    # 前端是: '/ws/snake/' + roomName + '/'
    # 所以这里匹配 ws/snake/任意字符/
    re_path(r'ws/snake/(?P<room_name>\w+)/$', SnakeConsumer.as_asgi()),
]