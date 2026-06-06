from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404  # 【修复1】补充缺失的导入
from django.contrib.auth.decorators import login_required

from .models import Topic, Entry, Comment, Like
from .forms import TopicForm, EntryForm


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

# views.py 示例片段
def topic(request, topic_id):
    topic = Topic.objects.get(id=topic_id)

    # 获取排序参数，默认为 '-date_added' (最新在前)
    order = request.GET.get('order', 'newest')

    if order == 'oldest':
        entries = topic.entry_set.order_by('date_added')
    else:
        entries = topic.entry_set.order_by('-date_added')

    context = {'topic': topic, 'entries': entries}
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
    """添加新条目"""
    topic = get_object_or_404(Topic, id=topic_id)

    if request.method != 'POST':
        form = EntryForm()
    else:
        form = EntryForm(data=request.POST)
        if form.is_valid():
            new_entry = form.save(commit=False)
            new_entry.topic = topic
            new_entry.owner = request.user      # 关联当前用户
            new_entry.save()
            return redirect('main_app:topic', topic_id=topic_id)

    context = {'topic': topic, 'form': form}
    return render(request, 'main_app/new_entry.html', context)
    # 【修复2】删除了原本在这里重复的死代码

def edit_entry(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)
    topic = entry.topic

    # 确保只有作者本人能编辑
    if entry.owner != request.user:
        raise Http404

    if request.method != 'POST':
        form = EntryForm(instance=entry)
    else:
        form = EntryForm(instance=entry, data=request.POST)
        if form.is_valid():
          form.save()
          return redirect('main_app:topic', topic_id=topic.id)

    context = {'entry': entry, 'topic': topic, 'form': form}
    return render(request, 'main_app/edit_entry.html', context)

@login_required
def add_comment(request, entry_id):
    entry = get_object_or_404(Entry, id=entry_id)

    if request.method == 'POST':
        # 【修复3】请务必检查你的 HTML 模板，input 或 textarea 的 name 属性必须也是 'content'
        # 如果你的 HTML 里写的是 name="text"，那这里就要改成 request.POST.get('text')
        content = request.POST.get('content')

        if content:
            Comment.objects.create(
                entry=entry,
                user=request.user,
                content=content # 确保 models.py 里 Comment 也有 content 字段
            )

    return redirect('main_app:topic', topic_id=entry.topic.id)


@login_required
def like_entry(request, entry_id):
    if request.method == 'POST':
        entry = get_object_or_404(Entry, id=entry_id)
        user = request.user

        # 1. 尝试查找当前用户是否已经点赞过这条帖子
        like_obj = Like.objects.filter(entry=entry, user=user).first()

        if like_obj:
            # 2. 如果找到了，说明是“取消点赞”，直接删除这条记录
            like_obj.delete()
        else:
            # 3. 如果没找到，说明是“新点赞”，创建一条新的 Like 记录
            Like.objects.create(entry=entry, user=user)

    # 4. 处理完回到原来的话题页面
    return redirect('main_app:topic', topic_id=entry.topic.id)

# 删除评论
@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    # 安全检查：只有评论作者或帖子作者才能删除
    if request.user == comment.user or request.user == comment.entry.owner:
        topic_id = comment.entry.topic.id
        comment.delete()
        return redirect('main_app:topic', topic_id=topic_id)
    return redirect('main_app:topic', topic_id=comment.entry.topic.id)

# 编辑评论 (简单版：直接提交新内容)
@login_required
def edit_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.method == 'POST':
        # 安全检查
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

    # 安全检查：只有作者能删
    if entry.owner != request.user:
        raise Http404

    if request.method == 'POST':
        entry.delete()
        return redirect('main_app:topic', topic_id=topic.id)

    # 如果是 GET 请求，可以显示一个确认页面，或者直接重定向回列表
    return redirect('main_app:topic', topic_id=topic.id)