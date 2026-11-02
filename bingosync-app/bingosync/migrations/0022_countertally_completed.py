from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0021_remove_user_review_style'),
    ]

    operations = [
        migrations.AddField(
            model_name='countertally',
            name='completed',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
