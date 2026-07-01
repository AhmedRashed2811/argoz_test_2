from django.db import migrations, models

from apps.companies.models import generate_api_key


def backfill_api_keys(apps, schema_editor):
    # Route to the DB being migrated: under a per-tenant `migrate --database=`,
    # the router has no tenant context and would otherwise hit `default`.
    db = schema_editor.connection.alias
    Company = apps.get_model("companies", "Company")
    for company in Company.objects.using(db).filter(api_key=""):
        company.api_key = generate_api_key()
        company.save(using=db, update_fields=["api_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0001_initial"),
    ]

    operations = [
        # Add nullable/blank first so existing rows don't collide on the unique
        # default, then backfill a distinct key per row.
        migrations.AddField(
            model_name="company",
            name="api_key",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.RunPython(backfill_api_keys, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="company",
            name="api_key",
            field=models.CharField(
                default=generate_api_key,
                help_text="Token external systems send to read this company's leads.",
                max_length=64,
                unique=True,
            ),
        ),
    ]
