from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zhang_jia", "0002_gameplayer_joined_at_gameroom_created_at_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="gameplayer",
            name="role",
            field=models.CharField(
                choices=[("wu_xie", "吴邪"), ("xiaoge", "张起灵"), ("pangzi", "王胖子")],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="gameplayer",
            constraint=models.UniqueConstraint(
                fields=("room", "user"), name="unique_player_per_room"
            ),
        ),
        migrations.AddConstraint(
            model_name="gameplayer",
            constraint=models.UniqueConstraint(
                fields=("room", "role"), name="unique_role_per_room"
            ),
        ),
    ]
