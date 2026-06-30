from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    # 核心：通过 OneToOneField 绑定到系统自带的 User
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # 把你想要的字段加在这里
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.CharField(max_length=200, blank=True, default="暂无签名")
    # 记录试炼比率，默认为28
    trial_rate = models.IntegerField(default=28) 
    # 记录是否通过试炼
    is_wang_member = models.BooleanField(default=False)

    best_memory_steps = models.IntegerField(default=99999, verbose_name="记忆训练最佳步数")
    best_minesweeper_time = models.IntegerField(default=0, verbose_name="黑课最佳成绩(秒)")
    best_snake_score = models.IntegerField(default=0, verbose_name="贪吃蛇最高分")

    def __str__(self):
        return f"{self.user.username}的档案"

class Friendship(models.Model):
    # 状态常量定义
    STATUS_PENDING = 0  # 待验证
    STATUS_ACCEPTED = 1 # 已通过

    STATUS_CHOICES = (
        (STATUS_PENDING, '待验证'),
        (STATUS_ACCEPTED, '已通过'),
    )

    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends_from')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friends_to')
    
    # 👇👇👇 新增状态字段 👇👇👇
    status = models.IntegerField(choices=STATUS_CHOICES, default=STATUS_PENDING)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 允许同一个 from_user 和 to_user 存在多条记录（比如一条是 pending，一条是 accepted 历史记录），
        # 但通常我们只关心最新的状态。为了简化，这里保留 unique_together 的逻辑可能需要调整，
        # 或者我们在代码逻辑里控制只创建一条。
        # 建议：保持唯一性约束，但在代码里先查有没有，有就更新状态，没有就创建。
        unique_together = ('from_user', 'to_user') 

    def __str__(self):
        return f"{self.from_user.username} -> {self.to_user.username} ({self.get_status_display()})"

class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages', verbose_name="发送者")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages', verbose_name="接收者")
    content = models.TextField(verbose_name="消息内容")
    is_read = models.BooleanField(default=False, verbose_name="是否已读")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="发送时间")

    class Meta:
        ordering = ['created_at'] # 默认按时间正序排列
        verbose_name = "私信记录"
        verbose_name_plural = "私信记录"

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username}: {self.content[:10]}..."