from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0023_user_obs_token_obs_room'),
    ]

    operations = [
        migrations.CreateModel(
            name='StarredSquare',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot', models.PositiveSmallIntegerField()),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='starred_squares', to='bingosync.game')),
                ('player', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='starred_squares', to='bingosync.player')),
            ],
        ),
        migrations.AddConstraint(
            model_name='starredsquare',
            constraint=models.UniqueConstraint(fields=('player', 'game', 'slot'), name='one_star_per_square'),
        ),
    ]
