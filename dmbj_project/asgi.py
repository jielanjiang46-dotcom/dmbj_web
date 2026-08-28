import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 确保环境变量设置正确
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dmbj_project.settings')

# 必须先初始化 Django 应用注册表，再导入会间接使用模型的 WebSocket 路由。
django_asgi_app = get_asgi_application()

from dmbj_project.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # 处理普通的 HTTP 请求 (网页访问)
    "http": django_asgi_app,

    # 处理 WebSocket 请求
    "websocket": AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns  # 引用下面的路由列表
        )
    ),
})
