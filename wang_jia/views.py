from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from accounts.models import UserProfile

@login_required
def wang_trial_view(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        # 1. 处理名字
        username = user.username
        if len(username) > 1:
            new_name = "汪" + username[1:]
        else:
            new_name = "汪" + username

        # 2. 获取答案
        ans1 = request.POST.get('founder', '').strip()
        ans2 = request.POST.get('enemy', '').strip()
        ans3 = request.POST.get('tattoo', '').strip()
        ans4 = request.POST.get('secret', '').strip()

        # 3. 计算比率
        rate = 28
        if ans1 != "汪藏海": rate += 1
        if ans2 != "东北张家": rate += 1
        if ans3 != "凤凰": rate += 1
        if ans4 != "长生术": rate += 1

        # 4. 彩蛋：如果有“张”字
        special_msg = ""  # <--- 【新增】先定义一个空字符串，防止后面报错

        if "张" in username:
            rate += 100
            special_msg = "检测到你有张家血脉，启动预警装置，比率自动＋100"

        # 5. 保存数据
        profile.trial_rate = rate
        profile.is_wang_member = (rate < 30)
        profile.save()

        # 6. 准备上下文
        context = {
            'new_name': new_name,
            'rate': rate,
            'is_passed': profile.is_wang_member,
            'special_msg': special_msg  # <--- 【新增】必须把这行加上！否则HTML收不到
        }

        # --- 关键点：这里必须确保路径正确 ---
        # 建议先打印一下，看看能不能找到文件
        try:
            return render(request, 'wang_jia/trial_result.html', context)
        except Exception as e:
            print(f"渲染出错: {e}")
            # 临时调试用：如果找不到模板，直接返回文本证明逻辑跑通了
            return HttpResponse(f"逻辑跑通了！比率是: {rate}, 名字是: {new_name}。但是模板找不到: {e}")

    # GET 请求显示题目页
    return render(request, 'wang_jia/wang_trial.html')

# views.py

@login_required
def gutongjing(request):
    user = request.user

    # --- 1. 处理名字逻辑 (无论 GET 还是 POST 都需要) ---
    username = user.username
    if len(username) > 1:
        new_name = "汪" + username[1:]
    else:
        new_name = "汪" + username

    # --- 2. 获取 Profile ---
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        # 如果还没有档案，创建一个默认的，防止报错
        profile = UserProfile.objects.create(user=user)

    # --- 3. 处理 POST 请求 (如果有表单提交的话) ---
    if request.method == 'POST':
        # 这里处理你的试炼逻辑...
        # ...
        pass

    # --- 4. 渲染页面，必须把变量放进 context 字典里！---
    context = {
        'new_name': new_name,      # <--- 这一行最关键，把名字传过去
        'profile': profile         # 把档案也传过去，用于判断权限
    }

    return render(request, 'wang_jia/gutongjing.html', context)