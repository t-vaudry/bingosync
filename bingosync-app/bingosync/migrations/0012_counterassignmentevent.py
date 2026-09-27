# Generated migration for CounterAssignmentEvent model

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0011_add_claim_status_to_square'),
    ]

    operations = [
        migrations.CreateModel(
            name='CounterAssignmentEvent',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Sent')),
                ('player_color_value', models.IntegerField(choices=[(1, 'Orange'), (2, 'Red'), (3, 'Blue'), (4, 'Green'), (5, 'Purple'), (6, 'Navy'), (7, 'Teal'), (8, 'Brown'), (9, 'Pink'), (10, 'Yellow')])),
                ('counter_player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='counter_assignments_made', to='bingosync.player')),
                ('monitored_player', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='counter_assignments_received', to='bingosync.player')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='bingosync.player')),
            ],
            options={
                'abstract': False,
                'get_latest_by': 'timestamp',
            },
        ),
    ]
