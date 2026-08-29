import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Friendship, Notification
from .models import ForestProgress, GamePlayer, GameRoom
from .consumers import IronTriangleConsumer


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


class ForestTriangleCombatTests(TestCase):
    @staticmethod
    def _three_player_state():
        return {
            "rope": {"deployed": True, "pulling": True},
            "players": {
                "1": {"id": "1", "username": "wuxie", "role": GamePlayer.ROLE_WU_XIE},
                "2": {"id": "2", "username": "xiaoge", "role": GamePlayer.ROLE_XIAOGE},
                "3": {"id": "3", "username": "pangzi", "role": GamePlayer.ROLE_PANGZI},
            },
        }

    def test_xiaoge_melee_has_high_damage(self):
        player = {
            "role": GamePlayer.ROLE_XIAOGE, "x": 100, "y": 548,
            "facing": "right", "attack_cooldown": 0, "attack_flash": 0,
        }
        zombie = {"id": "z1", "x": 160, "y": 548, "hp": 100, "alive": True}
        state = {"zombies": [zombie], "explosions": []}
        IronTriangleConsumer._perform_attack(state, player)
        self.assertEqual(zombie["hp"], 58)

    def test_pangzi_explosive_damages_a_group_at_range(self):
        player = {
            "role": GamePlayer.ROLE_PANGZI, "x": 100, "y": 548,
            "facing": "right", "attack_cooldown": 0, "attack_flash": 0,
        }
        zombies = [
            {"id": "z1", "x": 320, "y": 548, "hp": 100, "alive": True},
            {"id": "z2", "x": 380, "y": 548, "hp": 100, "alive": True},
        ]
        state = {"zombies": zombies, "explosions": []}
        IronTriangleConsumer._perform_attack(state, player)
        self.assertEqual([zombie["hp"] for zombie in zombies], [55, 55])
        self.assertEqual(len(state["explosions"]), 1)

    def test_new_player_starts_with_only_first_level_unlocked(self):
        user = User.objects.create_user("new_explorer", password="secret123")
        progress = ForestProgress.objects.create(user=user)
        self.assertEqual(progress.highest_unlocked_level, 1)

    def test_third_level_drops_rope_and_keeps_all_ambushes_hidden(self):
        state = self._three_player_state()
        IronTriangleConsumer._load_third_level(state)

        self.assertNotIn("rope", state)
        self.assertNotIn("barriers", state)
        self.assertEqual(sum(ambush["count"] for ambush in state["ambushes"]), 8)
        self.assertNotIn("ambushes", IronTriangleConsumer._state_payload(state))
        self.assertNotIn("ambushes", IronTriangleConsumer._state_payload(state, full=True))

    def test_fourth_level_has_role_chain_and_clears_combat_state(self):
        state = self._three_player_state()
        state.update({"zombies": [{"id": "old"}], "ambushes": [{"x": 1}], "explosions": [{}]})
        state["players"]["1"]["hp"] = 12
        IronTriangleConsumer._load_fourth_level(state)

        self.assertEqual(state["level"], 4)
        self.assertNotIn("rope", state)
        self.assertNotIn("zombies", state)
        self.assertNotIn("ambushes", state)
        self.assertNotIn("hp", state["players"]["1"])
        self.assertEqual(
            state["level4_objectives"],
            {"counterweight": False, "sky_lever": False, "astrolabe": False},
        )
        self.assertEqual(len(state["moving_platforms"]), 3)
        self.assertEqual(len(state["swing_ropes"]), 2)

    def test_fourth_level_rope_swings_and_releases_with_momentum(self):
        player = {
            "id": "1", "x": 0, "y": 0, "vx": 0, "vy": 0,
            "grounded": False, "attached_rope": "test-rope",
            "input": {"left": False, "right": True},
        }
        rope = {
            "id": "test-rope", "anchor_x": 200, "anchor_y": 20,
            "length": 300, "angle": -.4, "angular_velocity": .015,
            "x": 0, "y": 0, "rider": "1",
        }
        state = {"players": {"1": player}, "swing_ropes": [rope]}
        IronTriangleConsumer._update_swing_ropes(state)

        self.assertNotEqual(rope["x"], 0)
        self.assertEqual(player["x"], rope["x"] - 16)
        IronTriangleConsumer._release_swing_rope(state, player, rope)
        self.assertIsNone(rope["rider"])
        self.assertNotIn("attached_rope", player)
        self.assertGreater(player["release_momentum_ticks"], 0)

    def test_idle_swing_rope_keeps_a_small_natural_motion(self):
        rope = {
            "id": "idle-rope", "anchor_x": 200, "anchor_y": 20,
            "length": 300, "angle": 0, "angular_velocity": 0,
            "idle_direction": 1, "x": 200, "y": 320, "rider": None,
        }
        IronTriangleConsumer._update_swing_ropes({"players": {}, "swing_ropes": [rope]})
        self.assertNotEqual(rope["angular_velocity"], 0)

    def test_pangzi_can_detach_level_two_rope_after_landing(self):
        state = {
            "rope": {"pulling": False, "deployed": True, "completed": True},
        }
        player = {"vy": 4}
        IronTriangleConsumer._detach_level_two_rope(state, player)

        self.assertFalse(state["rope"]["deployed"])
        self.assertFalse(state["rope"]["pulling"])
        self.assertEqual(player["vy"], 0)
