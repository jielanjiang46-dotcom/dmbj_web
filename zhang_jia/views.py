from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User 
import json
from .consumers import GAME_ROOMS
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from .models import GameRoom, GamePlayer
from accounts.models import Notification


# Create your views here.
def memory(request):
    return render(request, 'zhang_jia/memory.html')

# 1. 保存成绩的接口
@login_required
def update_memory_score(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_score = int(data.get('score', 0))
            user = request.user

            # 通过 request.user.profile 访问你的自定义模型
            # 为了防止某些老用户没有 profile 报错，我们加个安全判断
            if hasattr(user, 'profile'):
                profile = user.profile
                # 如果新步数更小，或者之前没玩过(99999)，就更新
                if new_score < profile.best_memory_steps:
                    profile.best_memory_steps = new_score
                    profile.save()
                    return JsonResponse({'status': 'success', 'new_record': True})
                
                return JsonResponse({'status': 'success', 'new_record': False})
            else:
                return JsonResponse({'status': 'error', 'msg': 'User profile not found'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)})

    return JsonResponse({'status': 'error', 'msg': 'Invalid method'})


# 2. 获取成绩的接口 (给个人主页用)
def get_memory_score(request):
    # 1. 从 URL 参数中获取目标用户名 (?username=xxx)
    target_username = request.GET.get('username')

    target_user = None

    # 2. 确定要查谁的数据
    if target_username:
        try:
            target_user = User.objects.get(username=target_username)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '用户不存在'}, status=404)
    else:
        # 如果没传用户名，默认查当前登录用户（兼容旧逻辑）
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'message': '未登录且未指定用户'}, status=403)
        target_user = request.user

    # 3. 查询分数
    score = 99999  # 默认值
    try:
        # 假设 Profile 和 User 是 OneToOneField 关联
        profile = target_user.profile
        score = profile.best_memory_steps
    except Exception as e:
        pass  # 如果没有 profile，保持默认分

    # 4. 返回 JSON
    return JsonResponse({
        'status': 'success',
        'score': score
    })

def gu_lou(request):
    return render(request, 'zhang_jia/gu_lou.html')

@login_required
def snake_game(request):
    """渲染张家古楼贪吃蛇页面"""
    try:
        profile = request.user.profile
        best_score = profile.best_snake_score
    except:
        best_score = 0

    return render(request, 'zhang_jia/snake.html', {
        'best_score': best_score
    })

@login_required
def api_snake_action(request):
    """处理贪吃蛇成绩提交"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            action = data.get('action')

            if action == 'submit_score':
                score = int(data.get('score', 0))
                profile = request.user.profile

                # 分数越高越好，只有打破记录才保存
                if score > profile.best_snake_score:
                    profile.best_snake_score = score
                    profile.save()
                    return JsonResponse({'status': 'success', 'message': '古楼机关已记录新纪录！'})

                return JsonResponse({'status': 'success', 'message': '未能打破古楼记录'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)

    return JsonResponse({'status': 'error'}, status=400)

@login_required
def get_snake_score(request):
    username = request.GET.get('username')
    try:
        user = User.objects.get(username=username)
        profile = user.profile
        score = profile.best_snake_score
        return JsonResponse({'status': 'success', 'score': score})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required   # <--- 【关键】加上这个，Django 就会自动识别当前登录用户
@require_GET     # <--- 限制只能 GET 请求
def api_snake_leaderboard(request):
    """
    获取指定房间的排行榜数据
    """
    # 1. 获取房间号
    room_name = request.GET.get('room_name')
    if not room_name:
        return JsonResponse({'status': 'error', 'message': '缺少房间号'}, status=400)

    # 2. 从全局游戏状态中查找房间
    room_data = GAME_ROOMS.get(room_name)
    
    # 3. 如果房间不存在或没人，返回空列表
    if not room_data:
        return JsonResponse({
            'status': 'success',
            'leaderboard': [],
            'my_username': request.user.username # 即使没房间，也可以告诉前端你是谁
        })

    # 4. 提取所有蛇的分数和用户名，并排序
    leaderboard = []
    for snake in room_data['snakes']:
        leaderboard.append({
            'username': snake['name'],
            'score': snake['score']
        })
    
    # 按分数从高到低排序
    leaderboard.sort(key=lambda x: x['score'], reverse=True)

    # 5. 【完美解决】现在 request.user 是真实的登录用户了
    current_user_name = request.user.username
    
    return JsonResponse({
        'status': 'success',
        'leaderboard': leaderboard,
        'my_username': current_user_name # <--- 前端拿到这个就能高亮显示了！
    })

@login_required
def game_lobby(request):

    # 1. 创建一个森林铁三角房间
    room = GameRoom.objects.create(
        host=request.user,
        game_type="forest_triangle"
    )


    # 2. 让当前用户成为吴邪
    GamePlayer.objects.create(
        room=room,
        user=request.user,
        role="wu_xie"
    )


    # 3. 打开页面，并把房间号交给前端
    return render(
        request,
        'zhang_jia/game_lobby.html',
        {
            'room_id': room.room_id
        }
    )

@login_required
@require_POST
def send_game_invite(request):
    """发送游戏邀请通知"""
    import json
    data = json.loads(request.body)
    target_user_id = data.get('target_user_id')
    role = data.get('role')
    room_id = data.get('room_id')
    
    # 创建一条通知记录（你需要一个 Notification 模型）
    # 或者复用 Friendship 表，加一个字段区分类型
    # 简单起见，先打印日志
    print(f"🔥 游戏邀请: {request.user.username} 邀请 {target_user_id} 担任 {role}，房间 {room_id}")
    
    return JsonResponse({'status': 'ok', 'msg': '邀请已发送'})

@login_required
@require_POST
def send_game_invite(request):

    data = json.loads(request.body)

    target_user_id = data.get('target_user_id')
    role = data.get('role')
    room_id = data.get('room_id')


    target_user = User.objects.get(
        id=target_user_id
    )


    Notification.objects.create(
        from_user=request.user,
        to_user=target_user,
        notification_type='game_invite',
        message=f"""
邀请你加入森林铁三角游戏

房间号:{room_id}

角色:{role}
"""
    )


    return JsonResponse({
        "status":"ok"
    })

@login_required
@require_POST
def accept_join(request):

    data = json.loads(request.body)

    room_id = data.get('room_id')


    try:
        room = GameRoom.objects.get(
            room_id=room_id
        )

        GamePlayer.objects.create(
            room=room,
            user=request.user,
            role="待选择"
        )


        return JsonResponse({
            "status":"ok",
            "room_id":room_id
        })


    except GameRoom.DoesNotExist:

        return JsonResponse({
            "status":"error",
            "msg":"房间不存在"
        },status=404)