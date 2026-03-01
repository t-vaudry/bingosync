# Generated migration to add unique constraint to email field

from django.db import migrations, models


def remove_duplicate_emails(apps, schema_editor):
    """
    Handle existing duplicate emails before adding unique constraint.
    Keep the oldest account for each email and set duplicates/blanks to NULL.
    """
    User = apps.get_model('bingosync', 'User')
    db_alias = schema_editor.connection.alias
    
    # First, convert all empty string emails to NULL
    User.objects.using(db_alias).filter(email='').update(email=None)
    
    # Find all emails that have duplicates
    from django.db.models import Count
    duplicate_emails = (
        User.objects.using(db_alias)
        .values('email')
        .annotate(count=Count('id'))
        .filter(count__gt=1, email__isnull=False)
    )
    
    for item in duplicate_emails:
        email = item['email']
        # Get all users with this email, ordered by date_joined (oldest first)
        users_with_email = User.objects.using(db_alias).filter(email=email).order_by('date_joined')
        
        # Keep the first (oldest) user, set email to NULL for the rest
        for user in users_with_email[1:]:
            user.email = None
            user.save(using=db_alias)


class Migration(migrations.Migration):

    dependencies = [
        ('bingosync', '0006_remove_player_is_spectator'),
    ]

    operations = [
        # First, handle any existing duplicate emails
        migrations.RunPython(
            remove_duplicate_emails,
            reverse_code=migrations.RunPython.noop
        ),
        # Then alter the email field to add unique constraint and allow NULL
        migrations.AlterField(
            model_name='user',
            name='email',
            field=models.EmailField(
                blank=True,
                null=True,
                help_text='Optional. Must be unique if provided.',
                max_length=254,
                unique=True,
                verbose_name='email address'
            ),
        ),
    ]
