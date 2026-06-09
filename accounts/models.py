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

    def __str__(self):
        return f"{self.user.username}的档案"