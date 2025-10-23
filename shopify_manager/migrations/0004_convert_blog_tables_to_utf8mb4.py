from django.db import migrations


def convert_tables_to_utf8mb4(apps, schema_editor):
    # Only run on MySQL/MariaDB backends
    if schema_editor.connection.vendor != 'mysql':
        return

    with schema_editor.connection.cursor() as cursor:
        tables = [
            'shopify_manager_shopifyblog',
            'shopify_manager_shopifyblogpost',
            'shopify_manager_shopifycollection',
            'shopify_manager_collectionseooptimization',
            'shopify_manager_shopifyproductcollection',
        ]
        for table in tables:
            cursor.execute(
                f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_manager', '0003_alter_shopifyblogpost_featured_image_url_and_more'),
    ]

    operations = [
        migrations.RunPython(convert_tables_to_utf8mb4, migrations.RunPython.noop),
    ]
