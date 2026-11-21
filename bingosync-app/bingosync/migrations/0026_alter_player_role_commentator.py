from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0025_colorevent_changed_by'),
    ]

    operations = [
        migrations.AlterField(
            model_name='player',
            name='role',
            field=models.CharField(choices=[('gamemaster', 'Gamemaster'), ('player', 'Player'), ('counter', 'Counter'), ('spectator', 'Spectator'), ('commentator', 'Commentator')], default='player', max_length=20, verbose_name='Role'),
        ),
    ]
