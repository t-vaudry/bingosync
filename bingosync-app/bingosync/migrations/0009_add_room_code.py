# Generated migration for adding room_code field

from django.db import migrations, models
import random
import string


def generate_room_codes(apps, schema_editor):
    """Generate room codes for existing rooms."""
    Room = apps.get_model('bingosync', 'Room')
    
    for room in Room.objects.all():
        # Generate unique code
        while True:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if not Room.objects.filter(room_code=code).exists():
                room.room_code = code
                room.save()
                break


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0008_add_user_to_player'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='room_code',
            field=models.CharField(
                max_length=8,
                help_text='Short code for joining room',
                null=True,
                blank=True
            ),
        ),
        migrations.RunPython(generate_room_codes, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='room',
            name='room_code',
            field=models.CharField(
                max_length=8,
                unique=True,
                db_index=True,
                help_text='Short code for joining room'
            ),
        ),
    ]
