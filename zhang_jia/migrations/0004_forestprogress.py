import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("zhang_jia", "0003_gameplayer_room_constraints"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ForestProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("highest_unlocked_level", models.PositiveSmallIntegerField(default=1)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="forest_progress", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
