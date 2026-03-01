# Generated manually for task 2.9 - Role Change Functionality

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0004_player_is_also_player_player_monitoring_player_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoleChangeEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Sent')),
                ('player_color_value', models.IntegerField(choices=[(1, 'Orange'), (2, 'Red'), (3, 'Blue'), (4, 'Green'), (5, 'Purple'), (6, 'Navy'), (7, 'Teal'), (8, 'Brown'), (9, 'Pink'), (10, 'Yellow')])),
                ('old_role', models.CharField(max_length=20)),
                ('new_role', models.CharField(max_length=20)),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bingosync.player')),
                ('target_player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='role_change_targets', to='bingosync.player')),
            ],
            options={
                'get_latest_by': 'timestamp',
                'abstract': False,
            },
        ),
    ]
