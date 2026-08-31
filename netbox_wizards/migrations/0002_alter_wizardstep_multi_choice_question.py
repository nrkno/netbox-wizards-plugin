from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_wizards", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="wizardstep",
            name="multi_choice_question",
            field=models.CharField(
                blank=True,
                help_text="The prompt shown above the choice buttons, e.g. 'What type of resource do you want to delete?'.",
                max_length=200,
            ),
        ),
    ]
