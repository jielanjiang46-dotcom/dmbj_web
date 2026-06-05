from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import AuthenticationForm  # 引入Django自带登录表单
from django.contrib import messages

def index(request):
    # 1. 如果用户已经登录，直接渲染欢迎界面
    if request.user.is_authenticated:
        return render(request, 'index.html', {'user': request.user})

    # 2. 如果用户未登录，且点击了登录按钮（POST请求）
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # 登录成功，重定向回首页（此时 is_authenticated 为 True，会显示欢迎语）
            return redirect('main_app:index')
        else:
            # 登录失败，提示错误（比如密码不对）
            messages.error(request, "用户名或密码错误，请重试。")

    # 3. 如果是第一次访问（GET请求），或者是登录失败，显示空表单
    else:
        form = AuthenticationForm()

    # 4. 渲染首页，把表单传过去
    return render(request, 'index.html', {'form': form})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # 注册成功后自动登录
            return redirect('main_app:index') # 跳转到首页
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})