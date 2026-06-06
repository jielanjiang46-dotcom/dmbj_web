from django.db import models
from django.contrib.auth.models import User # 1. 引入 User 模型

class Topic(models.Model):
    text = models.CharField(max_length=200)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text

class Entry(models.Model):
    """学到的有关某个主题的具体知识"""
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE)

    # 2. 新增 owner 字段，关联 User，允许为空(为了兼容旧数据)，设置级联删除
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    text = models.TextField()
    date_added = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'entries'

    def __str__(self):
        return f"{self.text[:50]}..."

class Comment(models.Model):
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='comments')
    # 这里的 user 字段必须有！如果你的模型里叫 author，那 views.py 也要改
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username}"

# 【重点】检查你的 Like 模型
class Like(models.Model):
    # 这里的 user 和 entry 顺序很重要
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'entry')  # 防止重复点赞

    def __str__(self):
        return f"{self.user.username} likes {self.entry}"