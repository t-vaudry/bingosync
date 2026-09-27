# Generated migration to remove is_also_player field from Player model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0009_add_room_code'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='player',
            name='is_also_player',
        ),
    ]
