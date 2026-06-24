from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User  # <--- 【关键】必须加上这一行！
import json

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