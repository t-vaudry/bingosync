from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0024_starredsquare'),
    ]

    operations = [
        migrations.AddField(
            model_name='colorevent',
            name='changed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='color_changes_made', to='bingosync.player'),
        ),
    ]
