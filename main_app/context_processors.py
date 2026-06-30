# main_app/context_processors.py

import json
from django.db.models import Q
from accounts.models import Friendship # 确保导入你的 Friendship 模型

def global_chat_data(request):
    """
    这个处理器会为每个请求的模板上下文添加好友列表数据
    """
    # 如果用户未登录，返回空列表
    if not request.user.is_authenticated:
        return {'friends_json': '[]'}

    # 查询当前用户所有已接受的好友关系
    my_friends_query = Friendship.objects.filter(
        Q(from_user=request.user, status=Friendship.STATUS_ACCEPTED) |
        Q(to_user=request.user, status=Friendship.STATUS_ACCEPTED)
    )

    # 提取好友的用户ID
    friend_ids = set()
    for f in my_friends_query:
        if f.from_user_id != request.user.id:
            friend_ids.add(f.from_user_id)
        if f.to_user_id != request.user.id:
            friend_ids.add(f.to_user_id)

    # 获取好友的用户名和ID，并构造成前端需要的格式
    # 注意：这里需要从 django.contrib.auth.models 导入 User
    from django.contrib.auth.models import User
    friends_list = User.objects.filter(id__in=friend_ids)
    friends_data = [{"id": u.id, "username": u.username} for u in friends_list]

    # 返回一个字典，键名 'friends_json' 必须和模板中使用的变量名一致
    return {'friends_json': json.dumps(friends_data)}