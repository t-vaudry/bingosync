from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0022_countertally_completed'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='obs_token',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='user',
            name='obs_room',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='obs_users', to='bingosync.room'),
        ),
        migrations.AddField(
            model_name='player',
            name='obs_token',
            field=models.CharField(blank=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.CreateModel(
            name='CardReveal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='card_reveals', to='bingosync.game')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='card_reveals', to='bingosync.player')),
            ],
        ),
        migrations.AddConstraint(
            model_name='cardreveal',
            constraint=models.UniqueConstraint(fields=('player', 'game'), name='one_card_reveal_per_game'),
        ),
    ]
