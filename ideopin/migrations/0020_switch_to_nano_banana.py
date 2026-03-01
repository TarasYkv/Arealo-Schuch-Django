# Generated migration to switch all users to cheaper Nano Banana model

from django.db import migrations


def switch_to_nano_banana(apps, schema_editor):
    """Switch all PinSettings to use Nano Banana (cheaper) instead of Pro"""
    PinSettings = apps.get_model('ideopin', 'PinSettings')
    
    # Update all settings that use the expensive Pro model
    updated = PinSettings.objects.filter(
        gemini_model='gemini-3-pro-image-preview'
    ).update(gemini_model='gemini-2.5-flash-image')
    
    print(f"Updated {updated} IdeoPin settings to use Nano Banana (cheaper model)")


def revert_to_pro(apps, schema_editor):
    """Revert to Pro model (in case needed)"""
    PinSettings = apps.get_model('ideopin', 'PinSettings')
    PinSettings.objects.filter(
        gemini_model='gemini-2.5-flash-image'
    ).update(gemini_model='gemini-3-pro-image-preview')


class Migration(migrations.Migration):

    dependencies = [
        ('ideopin', '0019_alter_pinproject_pin_count'),
    ]

    operations = [
        migrations.RunPython(switch_to_nano_banana, revert_to_pro),
    ]
