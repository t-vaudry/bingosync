# Generated migration to remove is_spectator field

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0005_rolechangeevent'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='player',
            name='is_spectator',
        ),
    ]
