from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Comment, Entry, Topic


class CommentReplyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("wuxie", password="secret123")
        self.other = User.objects.create_user("xiaoge", password="secret123")
        self.topic = Topic.objects.create(text="新月饭店", owner=self.user)
        self.entry = Entry.objects.create(topic=self.topic, owner=self.user, text="帖子")
        self.client.force_login(self.user)

    def test_deep_reply_is_rendered_and_can_be_replied_to(self):
        root = Comment.objects.create(entry=self.entry, user=self.user, content="第一轮")
        reply = Comment.objects.create(
            entry=self.entry, user=self.other, content="第二轮", parent_comment=root
        )
        third = Comment.objects.create(
            entry=self.entry, user=self.user, content="第三轮", parent_comment=reply
        )

        response = self.client.get(reverse("main_app:topic", args=[self.topic.id]))

        self.assertContains(response, "第三轮")
        self.assertContains(
            response,
            f"setReplyTarget({self.entry.id}, {third.id}, &#x27;{self.user.username}&#x27;)",
        )

    def test_reply_parent_must_belong_to_submitted_entry(self):
        other_entry = Entry.objects.create(topic=self.topic, owner=self.user, text="另一帖子")
        unrelated = Comment.objects.create(entry=other_entry, user=self.other, content="别处评论")

        self.client.post(
            reverse("main_app:topic", args=[self.topic.id]),
            {"entry_id": self.entry.id, "parent_comment_id": unrelated.id, "content": "回复"},
        )

        created = Comment.objects.get(entry=self.entry, content="回复")
        self.assertIsNone(created.parent_comment)
