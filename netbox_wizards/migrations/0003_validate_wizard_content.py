from django.db import migrations, models

import netbox_wizards.validators


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_wizards", "0002_alter_wizardstep_multi_choice_question"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wizarddefinition",
            name="description",
            field=models.TextField(
                blank=True,
                help_text="Shown at the top of the wizard. Supports NetBox markdown (links, formatting).",
                validators=[netbox_wizards.validators.validate_safe_markdown],
            ),
        ),
        migrations.AlterField(
            model_name="wizardstep",
            name="instructions",
            field=models.TextField(
                blank=True,
                help_text="What the user needs to do for this step. Supports NetBox markdown, including links.",
                validators=[netbox_wizards.validators.validate_safe_markdown],
            ),
        ),
        migrations.AlterField(
            model_name="wizardstep",
            name="link_url",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Optional URL for this step, e.g. a NetBox Script, a NetBox object, or an external document."
                ),
                max_length=500,
                validators=[netbox_wizards.validators.validate_safe_link_url],
            ),
        ),
    ]
