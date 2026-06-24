import json
import random
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from accounts.models import UserProfile
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

# 辅助函数：安全获取用户档案，防止报错
def get_user_profile(user):
    try:
        return user.profile
    except UserProfile.DoesNotExist:
        return UserProfile.objects.create(user=user)

@login_required
def wang_trial_view(request):
    user = request.user
    profile = get_user_profile(user)

    if request.method == 'POST':
        # 1. 处理名字
        username = user.username
        new_name = "汪" + (username[1:] if len(username) > 1 else username)

        # 2. 获取答案
        ans1 = request.POST.get('founder', '').strip()
        ans2 = request.POST.get('enemy', '').strip()
        ans3 = request.POST.get('tattoo', '').strip()
        ans4 = request.POST.get('secret', '').strip()

        # 3. 计算比率 (基础分28，答错加分，分越低越好)
        rate = 28
        if ans1 != "汪藏海": rate += 1
        if ans2 != "东北张家": rate += 1
        if ans3 != "凤凰": rate += 1
        if ans4 != "长生术": rate += 1

        # 4. 彩蛋：如果有“张”字
        special_msg = ""
        if "张" in username:
            rate += 100
            special_msg = "检测到你有张家血脉，启动预警装置，比率自动＋100"

        # 5. 保存数据
        profile.trial_rate = rate
        profile.is_wang_member = (rate < 30)
        profile.save()

        context = {
            'new_name': new_name,
            'rate': rate,
            'is_passed': profile.is_wang_member,
            'special_msg': special_msg
        }
        return render(request, 'wang_jia/trial_result.html', context)

    return render(request, 'wang_jia/wang_trial.html')

@login_required
def gutongjing(request):
    user = request.user
    profile = get_user_profile(user)

    username = user.username
    new_name = "汪" + (username[1:] if len(username) > 1 else username)

    context = {
        'new_name': new_name,
        'profile': profile
    }
    return render(request, 'wang_jia/gutongjing.html', context)

@login_required
def minesweeper_page(request):
    """渲染扫雷游戏页面"""
    profile = get_user_profile(request.user)
    return render(request, 'wang_jia/minesweeper.html', {
        'best_time': profile.best_minesweeper_time
    })

@login_required
def api_minesweeper_action(request):
    """处理游戏核心逻辑：生成地图 或 提交成绩"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': '无效的请求数据'}, status=400)

    action = data.get('action')
    profile = get_user_profile(request.user)

    # --- 动作 1: 开始新游戏 ---
    if action == 'start':
        difficulty = data.get('difficulty', 'medium')
        rows = int(data.get('rows', 10))
        cols = int(data.get('cols', 10))
        mines_count = int(data.get('mines_count', 15))

        # 安全检查
        if rows > 30 or cols > 30 or mines_count > 200:
            return JsonResponse({'status': 'error', 'message': '阵法规模过大！'}, status=400)

        # 初始化网格
        grid = [[{
            'is_mine': False, 'count': 0, 'revealed': False, 'flagged': False
        } for _ in range(cols)] for _ in range(rows)]

        # 随机埋雷
        placed = 0
        while placed < mines_count:
            r, c = random.randint(0, rows - 1), random.randint(0, cols - 1)
            if not grid[r][c]['is_mine']:
                grid[r][c]['is_mine'] = True
                placed += 1

        # 计算周围雷数
        for r in range(rows):
            for c in range(cols):
                if grid[r][c]['is_mine']: continue
                count = sum(
                    1 for i in range(-1, 2) for j in range(-1, 2)
                    if 0 <= r+i < rows and 0 <= c+j < cols and grid[r+i][c+j]['is_mine']
                )
                grid[r][c]['count'] = count

        return JsonResponse({
            'status': 'success', 'grid': grid, 'rows': rows, 'cols': cols, 'difficulty': difficulty
        })

    # --- 动作 2: 提交成绩 ---
    elif action == 'submit_score':
        time_taken = int(data.get('time', 999))
        if profile.best_minesweeper_time == 0 or time_taken < profile.best_minesweeper_time:
            profile.best_minesweeper_time = time_taken
            profile.save()
            return JsonResponse({'status': 'success', 'message': '新纪录已保存！'})

        return JsonResponse({'status': 'success', 'message': '成绩未打破纪录'})

    return JsonResponse({'status': 'error'}, status=400)

@login_required  # <--- 添加这一行，强制要求登录
def api_get_minesweeper_score(request):
    target_username = request.GET.get('username', request.user.username)

    try:
        target_user = User.objects.get(username=target_username)
        profile = get_user_profile(target_user)
        best_time = profile.best_minesweeper_time

        if best_time == 0:
            return JsonResponse({'status': 'success', 'time': None, 'display_text': '暂无记录'})

        return JsonResponse({'status': 'success', 'time': best_time, 'display_text': f'{best_time}秒'})

    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '用户不存在'}, status=404)
    except Exception as e:
        # <--- 添加全局异常捕获，防止返回 HTML 报错页
        logger.error(f"获取扫雷分数失败: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '服务器内部错误'}, status=500)