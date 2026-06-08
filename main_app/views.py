from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from .models import Topic, Entry, Comment, Like
from .forms import TopicForm, EntryForm
from accounts.models import UserProfile

def index(request):
    """app的主页"""
    return render(request, 'main_app/index.html')

def navigation(request):
    return render(request, 'main_app/navigation.html')

def topics(request):
    """显示所有的主题"""
    topics = Topic.objects.order_by('date_added')
    context = {'topics': topics}
    return render(request, 'main_app/topics.html', context)

def topic(request, topic_id):
    """显示特定主题下的所有条目及其评论"""
    topic = get_object_or_404(Topic, id=topic_id)

    # 1. 获取排序参数
    order = request.GET.get('order', 'newest')
    if order == 'oldest':
        entries = topic.entry_set.order_by('date_added')
    else:
        entries = topic.entry_set.order_by('-date_added')

    # 2. 【新增】处理评论提交逻辑 (支持图片 + 回复)
    if request.method == 'POST' and 'content' in request.POST:
        content = request.POST.get('content')
        entry_id = request.POST.get('entry_id')
        parent_id = request.POST.get('parent_comment_id')

        if content and entry_id:
            target_entry = get_object_or_404(Entry, id=entry_id)
            parent_comment = None

            if parent_id:
                try:
                    parent_comment = Comment.objects.get(id=parent_id)
                except Comment.DoesNotExist:
                    pass

            new_comment = Comment.objects.create(
                entry=target_entry,
                user=request.user,
                content=content,
                parent_comment=parent_comment,
                image=request.FILES.get('image') # 接收上传的图片
            )
            return redirect('main_app:topic', topic_id=topic_id)

    context = {
        'topic': topic,
        'entries': entries,
    }
    return render(request, 'main_app/topic.html', context)

def new_topic(request):
    """添加新主题"""
    if request.method != 'POST':
        form = TopicForm()
    else:
        form = TopicForm(data=request.POST)
        if form.is_valid():
            form.save()
            return redirect('main_app:topics')

    context = {'form': form}
    return render(request, 'main_app/new_topic.html', context)

def new_entry(request, topic_id):
    topic = get_object_or_404(Topic, id=topic_id)

    if request.method != 'POST':
        form = EntryForm()
    else:
        # 【关键修复】必须传入 request.FILES 才能处理图片
        form = EntryForm(data=request.POST, files=request.FILES)

        if form.is_valid():
            new_entry = form.save(commit=False)
            new_entry.topic = topic
            new_entry.owner = request.user
            new_entry.save()
            return redirect('main_app:topic', topic_id=topic_id)

    context = {'topic': topic, 'form': form}
    return render(request, 'main_app/new_entry.html', context)

def edit_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)
    topic = entry.topic

    if entry.owner != request.user:
        raise Http404

    if request.method != 'POST':
        form = EntryForm(instance=entry)
    else:
        # 【重要修复】编辑时必须也要传入 files=request.FILES
        # 否则如果用户没重新选图，可能会出问题；如果选了图，不加这个也存不上
        form = EntryForm(instance=entry, data=request.POST, files=request.FILES)

        if form.is_valid():
            form.save()
            return redirect('main_app:topic', topic_id=topic.id)

    context = {'entry': entry, 'topic': topic, 'form': form}
    return render(request, 'main_app/edit_entry.html', context)

@login_required
def add_comment(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    if request.method == 'POST':
        content = request.POST.get('content')
        uploaded_image = request.FILES.get('image')
        parent_id = request.POST.get('parent_comment_id')

        if content or uploaded_image:
            parent_comment = None

            if parent_id and parent_id != '0':
                try:
                    parent_comment = Comment.objects.get(id=parent_id, entry=entry)
                except Comment.DoesNotExist:
                    parent_comment = None

            Comment.objects.create(
                entry=entry,
                user=request.user,
                content=content,
                image=uploaded_image,      # 【修复】修正了之前的拼写错误
                parent_comment=parent_comment
            )

    return redirect('main_app:topic', topic_id=entry.topic_id)

@login_required
def like_entry(request, entry_id):
    if request.method == 'POST':
        entry = get_object_or_404(Entry, id=entry_id)
        user = request.user

        like_obj = Like.objects.filter(entry=entry, user=user).first()

        if like_obj:
            like_obj.delete()
        else:
            Like.objects.create(entry=entry, user=user)

    return redirect('main_app:topic', topic_id=entry.topic.id)

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user == comment.user or request.user == comment.entry.owner:
        topic_id = comment.entry.topic.id
        comment.delete()
        return redirect('main_app:topic', topic_id=topic_id)
    return redirect('main_app:topic', topic_id=comment.entry.topic.id)

@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.method == 'POST':
        if request.user == comment.user:
            new_content = request.POST.get('content')
            if new_content:
                comment.content = new_content
                comment.save()
        return redirect('main_app:topic', topic_id=comment.entry.topic.id)

@login_required
def delete_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)
    topic = entry.topic

    if entry.owner != request.user:
        raise Http404

    if request.method == 'POST':
        entry.delete()
        return redirect('main_app:topic', topic_id=topic.id)

    return redirect('main_app:topic', topic_id=topic.id)

def user_profile(request, username):
    user_obj = get_object_or_404(User, username=username)
    profile, created = UserProfile.objects.get_or_create(user=user_obj)
    topics = user_obj.topics.all().order_by('-date_added')

    context = {
        'profile_user': user_obj,
        'profile': profile,
        'topics': topics,
        'is_me': request.user == user_obj
    }
    return render(request, 'main_app/profile.html', context)

@login_required
def edit_profile(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        bio = request.POST.get('bio')
        avatar = request.FILES.get('avatar')

        if bio is not None:
            profile.bio = bio
        if avatar:
            profile.avatar = avatar

        profile.save()
        return redirect('main_app:user_profile', username=request.user.username)

    return render(request, 'main_app/edit_profile.html', {'profile': profile})