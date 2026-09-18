from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_wizards", "0003_validate_wizard_content"),
    ]

    operations = [
        migrations.AddField(
            model_name="wizardstep",
            name="is_text_input",
            field=models.BooleanField(default=False, help_text="If checked, the user must enter a text answer before continuing."),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="answer_key",
            field=models.CharField(blank=True, help_text="Stable key used to reference this step's stored answer as '{{ answers.key }}'.", max_length=100),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="text_input_prompt",
            field=models.CharField(blank=True, help_text="Label shown above the text input.", max_length=200),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="text_input_placeholder",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="text_input_help",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="text_input_required",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="text_input_regex",
            field=models.CharField(blank=True, help_text="Optional regular expression which the complete answer must match.", max_length=500),
        ),
        migrations.AddField(
            model_name="wizardstep",
            name="text_input_validation_message",
            field=models.CharField(blank=True, help_text="Message shown when the answer does not match the validation expression.", max_length=500),
        ),
        migrations.AddField(
            model_name="wizardstepchoice",
            name="answer_value",
            field=models.CharField(blank=True, help_text="Stored answer value. If unset, the choice key is stored.", max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="wizardstepprogress",
            name="answer_value",
            field=models.CharField(blank=True, help_text="The answer captured for this step, if it produces a stored answer.", max_length=2000, null=True),
        ),
        migrations.AddConstraint(
            model_name="wizardstep",
            constraint=models.UniqueConstraint(condition=~models.Q(answer_key=""), fields=("definition", "answer_key"), name="wizards_unique_definition_answer_key"),
        ),
    ]
