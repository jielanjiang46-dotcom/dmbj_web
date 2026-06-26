import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 确保环境变量设置正确
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmbj_project.settings')

# 1. 引入我们即将创建的路由配置
# 注意：这里假设 routing.py 放在和 asgi.py 同级目录下 (即 dmbj_web/routing.py)
from dmbj_project.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # 处理普通的 HTTP 请求 (网页访问)
    "http": get_asgi_application(),

    # 处理 WebSocket 请求
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns  # 引用下面的路由列表
        )
    ),
})