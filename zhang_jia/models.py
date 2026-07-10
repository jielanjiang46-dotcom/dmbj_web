from django.db import models
from django.contrib.auth.models import User
import random
import string


class GameRoom(models.Model):

    # 房间号码，例如：A83KD92P
    room_id = models.CharField(
        max_length=20,
        unique=True,
        blank=True
    )

    # 房主（森林铁三角里固定是吴邪）
    host = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_game_rooms'
    )

    # 游戏类型
    # 例如：forest_triangle
    game_type = models.CharField(
        max_length=50
    )

    # 创建时间
    created_at = models.DateTimeField(
        auto_now_add=True
    )

    # 房间状态
    # waiting = 等待玩家
    # playing = 游戏中
    status = models.CharField(
        max_length=20,
        default="waiting"
    )


    def save(self, *args, **kwargs):

        # 如果没有房间号，自动生成
        if not self.room_id:

            self.room_id = ''.join(
                random.choices(
                    string.ascii_uppercase + string.digits,
                    k=8
                )
            )

        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.room_id} - {self.host.username}"



class GamePlayer(models.Model):

    # 属于哪个房间
    room = models.ForeignKey(
        GameRoom,
        on_delete=models.CASCADE,
        related_name='players'
    )

    # 哪个用户
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='game_players'
    )

    # 角色
    # wu_xie
    # zhang_qiling
    # pangzi
    role = models.CharField(
        max_length=20
    )


    # 加入时间
    joined_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return f"{self.user.username} - {self.role}"