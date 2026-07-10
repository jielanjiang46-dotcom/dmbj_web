from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from .models import Topic, Entry, Comment, Like
from .forms import TopicForm, EntryForm
from accounts.models import UserProfile, Friendship, Message, Notification  # 确保 Friendship 模型已导入
import json
from django.views.decorators.http import require_POST
from django.views.decorators.http import require_GET
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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

    # 2. 处理评论提交逻辑 (支持图片 + 回复)
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
                image=uploaded_image,
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

# --- 社交系统 API 接口 ---

@login_required
@require_POST  # 强制只能 POST 请求
def add_friend(request):
    try:
        # 1. 解析数据 (兼容 JSON 和 表单两种格式)
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            target_id = data.get('user_id')
        else:
            target_id = request.POST.get('user_id')

        if not target_id:
            return JsonResponse({'status': 'error', 'message': '缺少用户ID'})

        # 2. 查找用户
        target_user = User.objects.get(id=target_id)

        # 3. 逻辑检查
        if target_user == request.user:
            return JsonResponse({'status': 'error', 'message': '不能添加自己'})

        # 检查是否已存在关系 (双向检查)
        if Friendship.objects.filter(
            Q(from_user=request.user, to_user=target_user) | 
            Q(from_user=target_user, to_user=request.user)
        ).exists():
            return JsonResponse({'status': 'error', 'message': '你们已经是好友了'})

        # 4. 创建申请
        Friendship.objects.create(
            from_user=request.user, 
            to_user=target_user, 
            status=Friendship.STATUS_PENDING
        )

        # 【关键修改】这里不要 redirect！直接返回成功信息
        return JsonResponse({
            'status': 'success', 
            'message': f'已向 {target_user.username} 发送好友申请'
        })

    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '用户不存在'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})

@login_required
def search_user(request):
    """搜索用户接口 (GET)"""
    keyword = request.GET.get('q', '').strip()
    if not keyword:
        return JsonResponse({'status': 'error', 'message': '请输入搜索内容'})

    # 1. 先构建查询集 (Filter) - 此时不要切片
    # 注意：如果 keyword 是纯数字，Q(id=keyword) 没问题；如果是字符串，Q(id='abc') 可能会报错，建议做个判断或者用 try-except，但为了简单先保留原逻辑
    users_query = User.objects.filter(
        Q(username__icontains=keyword) | Q(id=keyword)
    )
    
    # 2. (可选) 如果有排序需求，必须在这里加，比如 .order_by('id')
    
    # 3. 检查是否存在 (Exists)
    if users_query.exists():
        # 4. 获取第一个用户 (First) - 这里不需要切片，first() 会自动处理
        user = users_query.first() 
        
        return JsonResponse({
            'status': 'success', 
            'user': {
                'id': user.id, 
                'username': user.username
            }
        })
    
    return JsonResponse({'status': 'error', 'message': '未找到该用户'})
    
def user_profile(request, username):
    # 1. 获取当前查看的用户对象
    user_obj = get_object_or_404(User, username=username)
    
    # 2. 获取或创建用户资料
    profile, created = UserProfile.objects.get_or_create(user=user_obj)
    
    # 3. 获取该用户的主题/帖子 (按时间倒序)
    topics = user_obj.topics.all().order_by('-date_added')

    # --- 【核心修复】初始化所有变量，防止 UnboundLocalError ---
    relation_status = 'none' 
    pending_requests_in = [] 
    friends_list = []
    friend_count = 0
    friends_json = '[]'  # 默认为空 JSON 字符串

    if request.user.is_authenticated:
        current_user = request.user
        
        # --- 情况 A：我看的是别人的主页 ---
        if current_user != user_obj:
            # 检查是否已经是双向好友
            is_mutual = Friendship.objects.filter(
                from_user=current_user, to_user=user_obj, status=Friendship.STATUS_ACCEPTED
            ).exists() and Friendship.objects.filter(
                from_user=user_obj, to_user=current_user, status=Friendship.STATUS_ACCEPTED
            ).exists()
            
            if is_mutual:
                relation_status = 'friends'
            else:
                # 检查我是否发过申请（单向）
                sent_request = Friendship.objects.filter(
                    from_user=current_user, to_user=user_obj, status=Friendship.STATUS_PENDING
                ).exists()
                
                if sent_request:
                    relation_status = 'pending_sent'
                else:
                    # 检查对方是否发过申请给我
                    received_request = Friendship.objects.filter(
                        from_user=user_obj, to_user=current_user, status=Friendship.STATUS_PENDING
                    ).exists()
                    
                    if received_request:
                        relation_status = 'pending_received'
                    else:
                        relation_status = 'none'

        # --- 情况 B：我看的是自己的主页 ---
        else:
            # 1. 获取待处理的好友申请
            pending_requests_in = Friendship.objects.filter(
                to_user=current_user, 
                status=Friendship.STATUS_PENDING
            ).select_related('from_user')

            # 2. 获取真正的好友列表 (双向 STATUS_ACCEPTED)
            # 查找所有与我有关且状态为 ACCEPTED 的记录
            my_friends_query = Friendship.objects.filter(
                Q(from_user=current_user, status=Friendship.STATUS_ACCEPTED) | 
                Q(to_user=current_user, status=Friendship.STATUS_ACCEPTED)
            )
            
            # 提取好友 ID (排除我自己)
            ids = set()
            for f in my_friends_query:
                if f.from_user_id != current_user.id:
                    ids.add(f.from_user_id)
                if f.to_user_id != current_user.id:
                    ids.add(f.to_user_id)
                
            # 批量获取好友对象
            friends_list = User.objects.filter(id__in=ids)
            friend_count = friends_list.count()
            
            # 3. 【关键】生成 JSON 数据供前端 JS 使用
            friends_data = [{"id": u.id, "username": u.username} for u in friends_list]
            friends_json = json.dumps(friends_data)

    context = {
        'profile_user': user_obj,
        'profile': profile,
        'topics': topics,
        'is_me': request.user == user_obj,
        
        # 关系状态
        'relation_status': relation_status, 
        
        # 待处理申请
        'pending_requests_in': pending_requests_in,
        
        # 好友相关数据
        'friends_list': friends_list,
        'friend_count': friend_count,
        'friends_json': friends_json, # 确保这个变量永远存在
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

@login_required
@require_POST
def send_friend_request(request):
    """发送好友申请"""
    try:
        data = json.loads(request.body)
        target_username = data.get('username')
        target_user = User.objects.get(username=target_username)
        
        if target_user == request.user:
            return JsonResponse({'status': 'error', 'msg': '不能添加自己'})

        # 检查是否已经是好友（双向都通过）
        is_friend = Friendship.objects.filter(
            from_user=request.user, to_user=target_user, status=Friendship.STATUS_ACCEPTED
        ).exists() or Friendship.objects.filter(
            from_user=target_user, to_user=request.user, status=Friendship.STATUS_ACCEPTED
        ).exists()

        if is_friend:
            return JsonResponse({'status': 'error', 'msg': '你们已经是好友了'})

        # 👇👇👇 核心修改：使用 get_or_create，并设置默认状态为 PENDING 👇👇👇
        friendship, created = Friendship.objects.get_or_create(
            from_user=request.user,
            to_user=target_user,
            defaults={'status': Friendship.STATUS_PENDING} # 如果是新创建的，默认为待验证
        )

        # 如果记录已存在但不是 Pending (比如之前被拒绝过，或者逻辑上有残留)，强制更新为 Pending
        if not created and friendship.status != Friendship.STATUS_PENDING:
             # 这里可以根据业务需求决定：是覆盖旧状态，还是提示“已发送过申请”
             # 简单起见，我们假设重新发送会重置状态
             friendship.status = Friendship.STATUS_PENDING
             friendship.save()

        return JsonResponse({'status': 'success', 'msg': '好友申请已发送，等待对方通过'})

    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': '用户不存在'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)})


@login_required
@require_POST
def accept_friend(request):
    """
    用户点击“通过”时调用。
    现在从 POST 表单中获取 user_id，而不是从 URL 获取。
    """
    # 1. 从表单数据中获取 ID
    target_user_id = request.POST.get('user_id') 
    
    if not target_user_id:
        return JsonResponse({'status': 'error', 'message': '缺少用户ID'})

    try:
        # 2. 找到那条“别人发给我”的待验证记录
        friendship = Friendship.objects.get(
            from_user_id=target_user_id,
            to_user=request.user,
            status=Friendship.STATUS_PENDING
        )
        
        # 3. 更新状态为“已通过”
        friendship.status = Friendship.STATUS_ACCEPTED
        friendship.save()
        
        # 4. (推荐) 自动创建一条反向记录，方便以后查询
        Friendship.objects.get_or_create(
            from_user=request.user,
            to_user_id=target_user_id,
            defaults={'status': Friendship.STATUS_ACCEPTED}
        )
        
    except Friendship.DoesNotExist:
        pass # 如果记录不存在（可能重复点击），忽略错误

    # 5. 处理完后，重定向回当前用户的主页
    # 注意：这里假设你是想刷新页面看列表变化。如果是 AJAX 请求，应该返回 JsonResponse
    # 为了配合你之前的 HTML form action，这里保持 redirect
    return redirect('main_app:user_profile', username=request.user.username)

@login_required
@require_POST
def reject_friend(request):
    """
    功能：拒绝好友申请（或者删除已存在的好友关系）
    """
    # 1. 从表单获取 ID
    target_user_id = request.POST.get('user_id')

    if not target_user_id:
        return JsonResponse({'status': 'error', 'message': '缺少用户ID'})

    try:
        # 尝试找到这条关系记录并删除
        # 无论是 Pending 还是 Accepted，直接删掉就是拒绝/绝交
        friendship = Friendship.objects.get(
            Q(from_user_id=target_user_id, to_user=request.user) | 
            Q(from_user=request.user, to_user_id=target_user_id)
        )
        friendship.delete()
    except Friendship.DoesNotExist:
        pass # 没找到就不做任何事
    
    # 刷新当前页面
    return redirect('main_app:user_profile', username=request.user.username)

@login_required
@require_POST
def cancel_friend_request(request):
    """取消我发出的好友申请"""
    # 从表单获取对方的 ID
    target_user_id = request.POST.get('user_id')
    if not target_user_id:
        return JsonResponse({'status': 'error', 'message': '缺少用户ID'})

    try:
        friendship = Friendship.objects.get(
            from_user=request.user,
            to_user_id=target_user_id,
            status=Friendship.STATUS_PENDING
        )
        friendship.delete()
    except Friendship.DoesNotExist:
        pass
        
    return redirect('main_app:user_profile', username=request.user.username)


@login_required
@require_POST
def remove_friend(request):
    """
    功能：删除好友（双向删除）
    逻辑：A和B是好友，A点击删除，需要删掉 A->B 和 B->A 两条记录
    改动：从 request.POST 获取 user_id，不再依赖 URL 参数
    """
    # 1. 从 POST 数据中获取对方 ID
    target_user_id = request.POST.get('user_id')
    
    if not target_user_id:
        # 如果没有 ID，通常重定向回原页面或者报错，这里选择安全地重定向
        return redirect('main_app:user_profile', username=request.user.username)

    try:
        # 2. 删除 "我 -> 他" 的记录
        f1 = Friendship.objects.get(from_user=request.user, to_user_id=target_user_id)
        f1.delete()
        
        # 3. 删除 "他 -> 我" 的记录
        f2 = Friendship.objects.get(from_user_id=target_user_id, to_user=request.user)
        f2.delete()
        
    except Friendship.DoesNotExist:
        # 如果找不到记录（可能已经删过了），不做任何事，防止报错
        pass
        
    # 4. 操作完成后，刷新当前用户的主页
    return redirect('main_app:user_profile', username=request.user.username)

@login_required
@require_POST
def send_message_api(request):
    try:
        data = json.loads(request.body)
        partner_id = data.get('partner_id')
        content = data.get('content')

        if not partner_id or not content:
            return JsonResponse({'status': 'error', 'msg': '参数缺失'}, status=400)

        # 创建并保存消息
        Message.objects.create(
            sender=request.user,
            receiver_id=partner_id, # 直接使用 ID 查询，效率更高
            content=content
        )

        return JsonResponse({'status': 'ok', 'msg': '发送成功'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)

@login_required
def get_messages_api(request):
    """获取与特定用户的聊天记录"""
    partner_id = request.GET.get('partner_id')
    
    if not partner_id:
        return JsonResponse({'status': 'error', 'msg': '缺少对方ID'}, status=400)

    try:
        # 查找“我发给他的”或者“他发给我的”消息
        messages = Message.objects.filter(
            (Q(sender=request.user) & Q(receiver_id=partner_id)) |
            (Q(sender_id=partner_id) & Q(receiver=request.user))
        ).order_by('created_at') # 按时间正序排列

        # 将查询集转换为列表字典，方便前端 JSON 解析
        data = []
        for msg in messages:
            data.append({
                'id': msg.id,
                'content': msg.content,
                'sender_id': msg.sender.id,
                'is_me': msg.sender == request.user, # 标记是不是自己发的
                'time': msg.created_at.strftime('%H:%M')
            })

        return JsonResponse({'status': 'ok', 'data': data})

    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)

# ... 其他代码不变 ...
@login_required
def check_unread_count(request):
    """ 检查当前用户所有未读消息的总数 """
    unread_count = Message.objects.filter(receiver=request.user, is_read=False).count()
    return JsonResponse({
        'status': 'ok',
        'chat_unread': unread_count  # ✅ 就改这里！把 'unread_count' 改成 'chat_unread'
    })


@login_required
def get_friends_api(request):
    """
    API: 获取当前用户的好友列表
    """
    try:
        # 1. 找到所有与当前用户有关，且状态为“已通过”的好友关系
        friendships = Friendship.objects.filter(
            Q(from_user=request.user, status=Friendship.STATUS_ACCEPTED) |
            Q(to_user=request.user, status=Friendship.STATUS_ACCEPTED)
        )

        # 2. 提取出真正的好友对象（使用 set 自动去重）
        unique_friends = set()
        for f in friendships:
            if f.from_user == request.user:
                unique_friends.add(f.to_user)
            else:
                unique_friends.add(f.from_user)

        # 3. 将好友数据整理成 JSON 格式
        friends_data = []
        
        # 【注意】确保 media/avatars/ 下确实有这张图
        DEFAULT_AVATAR = '/media/avatars/default.jpg' 

        for user in unique_friends:
            avatar_url = DEFAULT_AVATAR
            
            try:
                # 【核心修改点】
                # 根据你的 models.py，关联名是 'profile' 而不是 'userprofile'
                # hasattr 检查是否存在 profile 对象，and 后面检查 avatar 字段是否有值
                if hasattr(user, 'profile') and user.profile.avatar:
                    real_url = user.profile.avatar.url
                    if real_url:
                        avatar_url = real_url
            except (ValueError, AttributeError, OSError) as e:
                # 如果出错（例如文件丢失），打印错误以便调试，并继续使用默认头像
                print(f"获取用户 {user.username} 头像失败: {e}")
                pass

            friends_data.append({
                'id': user.id,
                'username': user.username,
                'avatar': avatar_url,
                # 补充 is_online 字段
                'is_online': getattr(user, 'is_active', False) 
            })

        return JsonResponse({'status': 'ok', 'friends': friends_data})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)
# 在 from djang.txt 文件中添加这个新函数

import logging
logger = logging.getLogger('django')

@login_required
@require_POST
def mark_messages_as_read(request):
    """
    标记与特定用户的所有消息为已读
    """
    try:
        data = json.loads(request.body)
        # 强制把 partner_id 转为字符串，防止类型不匹配
        partner_id = str(data.get('partner_id')) 
        
        logger.info(f"🔥 收到标记已读请求，聊天对象ID: {partner_id}")

        # 找到所有“对方发给我”且“未读”的消息
        unread_messages = Message.objects.filter(
            sender_id=partner_id,
            receiver=request.user,
            is_read=False
        )

        # 看看到底查到了几条未读消息
        count = unread_messages.count()
        logger.info(f"🔍 找到未读消息数量: {count}")

        # 批量更新为已读
        unread_messages.update(is_read=True)

        return JsonResponse({'status': 'ok', 'msg': f'成功标记 {count} 条消息为已读'})

    except Exception as e:
        logger.error(f"❌ 标记已读出错: {str(e)}")
        return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)

# 在你的 views.py 文件中添加

@login_required
@require_GET
def get_notification_requests(request):
    """
    获取当前用户收到的所有未读通知（好友申请、游戏邀请等）
    """
    notifications = Notification.objects.filter(
        to_user=request.user, 
        is_read=False
    ).select_related('from_user')  # select_related 优化查询性能，避免 N+1 问题

    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'from_user': {
                'id': n.from_user.id,
                'username': n.from_user.username,
                'avatar': n.from_user.avatar.url if hasattr(n.from_user, 'avatar') and n.from_user.avatar else None
            },
            'type': n.notification_type,
            'message': n.message,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
        
    return JsonResponse({'status': 'ok', 'data': data})


@login_required
@require_POST
def send_game_invite(request):
    """
    发送游戏邀请（写入 Notification 表）
    """
    try:
        body = json.loads(request.body)
        target_user_id = body.get('target_user_id')
        role = body.get('role')
        room_id = body.get('room_id')
        
        target_user = User.objects.get(id=target_user_id)
        
        # 创建一条游戏邀请通知
        Notification.objects.update_or_create(
            from_user=request.user,
            to_user=target_user,
            notification_type='game_invite',
            defaults={
                'message': json.dumps({'role': role, 'room_id': room_id}),
                'is_read': False
            }
        )
        
        print(f"🔥 [游戏邀请] {request.user.username} -> {target_user.username}, 房间: {room_id}")
        return JsonResponse({'status': 'ok', 'msg': '邀请已发送'})
        
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'msg': '目标用户不存在'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)

@login_required
@require_POST
def accept_join_request(request):
    """
    处理【同意加入】的逻辑
    前端传参: { "room_id": "xxx", "requester_id": 123 }
    """
    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')
        requester_id = data.get('requester_id') # 想要加入的人的ID
        
        # TODO: 这里你应该去数据库把那个 Notification 标记为已读/已处理
        # Notification.objects.filter(...).update(is_read=True, status='accepted')

        # 【关键步骤】通过 WebSocket 广播消息
        # 告诉房间里所有人：这个人加入了！
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"game_room_{room_id}", # 发送给特定的房间组
            {
                "type": "user_joined", # 对应 consumers.py 里的方法名
                "message": {
                    "action": "join_success",
                    "user_id": requester_id,
                    "username": request.user.username # 或者是 requester 的名字，看你怎么查
                }
            }
        )

        return JsonResponse({'status': 'ok', 'msg': '邀请已通过'})

    except Exception as e:
        return JsonResponse({'status': 'error', 'msg': str(e)}, status=500)