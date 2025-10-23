from django.db import migrations


def convert_more_tables_to_utf8mb4(apps, schema_editor):
    if schema_editor.connection.vendor != 'mysql':
        return

    tables = [
        'shopify_manager_shopifycollection',
        'shopify_manager_collectionseooptimization',
        'shopify_manager_shopifyproductcollection',
        'shopify_manager_shopifyproduct',
        'shopify_manager_productseooptimization',
        'shopify_manager_shopifyproductimage',
        'shopify_manager_productshippingprofile',
        'shopify_manager_googleadsproductdata',
    ]

    with schema_editor.connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                f"ALTER TABLE {table} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('shopify_manager', '0004_convert_blog_tables_to_utf8mb4'),
    ]

    operations = [
        migrations.RunPython(convert_more_tables_to_utf8mb4, migrations.RunPython.noop),
    ]

