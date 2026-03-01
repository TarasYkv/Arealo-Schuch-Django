# Generated migration to switch all users to cheaper Nano Banana model

from django.db import migrations


def switch_to_nano_banana(apps, schema_editor):
    """Switch all BlogPrepSettings to use Nano Banana (cheaper) instead of Pro"""
    BlogPrepSettings = apps.get_model('blogprep', 'BlogPrepSettings')
    
    # Update all settings that use the expensive Pro model
    updated = BlogPrepSettings.objects.filter(
        image_model='gemini-3-pro-image-preview'
    ).update(image_model='gemini-2.5-flash-image')
    
    print(f"Updated {updated} settings to use Nano Banana (cheaper model)")


def revert_to_pro(apps, schema_editor):
    """Revert to Pro model (in case needed)"""
    BlogPrepSettings = apps.get_model('blogprep', 'BlogPrepSettings')
    BlogPrepSettings.objects.filter(
        image_model='gemini-2.5-flash-image'
    ).update(image_model='gemini-3-pro-image-preview')


class Migration(migrations.Migration):

    dependencies = [
        ('blogprep', '0006_add_custom_update_days'),
    ]

    operations = [
        migrations.RunPython(switch_to_nano_banana, revert_to_pro),
    ]
