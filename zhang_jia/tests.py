import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Friendship, Notification
from .models import GamePlayer, GameRoom


class ForestTriangleFlowTests(TestCase):
    def setUp(self):
        self.host = User.objects.create_user("wuxie", password="secret123")
        self.xiaoge = User.objects.create_user("xiaoge", password="secret123")
        Friendship.objects.create(
            from_user=self.host,
            to_user=self.xiaoge,
            status=Friendship.STATUS_ACCEPTED,
        )

    def test_host_creates_room_and_occupies_wu_xie_role(self):
        self.client.force_login(self.host)
        response = self.client.get(reverse("zhang_jia:game_lobby"))
        room = GameRoom.objects.get(host=self.host)
        self.assertRedirects(response, reverse("zhang_jia:game_room", args=[room.room_id]))
        self.assertTrue(room.players.filter(user=self.host, role=GamePlayer.ROLE_WU_XIE).exists())

    def test_invited_friend_joins_the_assigned_role(self):
        room = GameRoom.objects.create(host=self.host, game_type="forest_triangle")
        GamePlayer.objects.create(room=room, user=self.host, role=GamePlayer.ROLE_WU_XIE)
        self.client.force_login(self.host)
        invite_response = self.client.post(
            reverse("zhang_jia:send_game_invite"),
            data=json.dumps({
                "target_user_id": self.xiaoge.id,
                "room_id": room.room_id,
                "role": GamePlayer.ROLE_XIAOGE,
            }),
            content_type="application/json",
        )
        self.assertEqual(invite_response.status_code, 200)
        notification = Notification.objects.get(to_user=self.xiaoge)

        self.client.force_login(self.xiaoge)
        join_response = self.client.post(
            reverse("zhang_jia:accept_join"),
            data=json.dumps({"notification_id": notification.id}),
            content_type="application/json",
        )
        self.assertEqual(join_response.status_code, 200)
        self.assertTrue(room.players.filter(user=self.xiaoge, role=GamePlayer.ROLE_XIAOGE).exists())
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

    def test_non_member_cannot_open_room_url(self):
        room = GameRoom.objects.create(host=self.host, game_type="forest_triangle")
        GamePlayer.objects.create(room=room, user=self.host, role=GamePlayer.ROLE_WU_XIE)
        self.client.force_login(self.xiaoge)
        response = self.client.get(reverse("zhang_jia:game_room", args=[room.room_id]))
        self.assertRedirects(response, reverse("main_app:navigation"))
