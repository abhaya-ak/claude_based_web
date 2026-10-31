from django.db import migrations


def seed_default_scanner_config(apps, schema_editor):
    ScannerConfig = apps.get_model("scanner", "ScannerConfig")
    ScannerConfig.objects.get_or_create(
        id=1,
        defaults={
            "keyword_cap_points": 45,
            "ip_url_points": 25,
            "prior_pending_points": 20,
            "high_priority_threshold": 75,
            "ruleset_version": 1,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("scanner", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            seed_default_scanner_config,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
