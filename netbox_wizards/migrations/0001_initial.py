"""
Squashed initial migration for the netbox_wizards plugin. Combines the full
schema from the original 0001_initial, the empty 0002, and 0003_multi_choice
into a single clean migration:

  WizardDefinition, WizardStep (with multi-choice fields), WizardStepImage,
  WizardStepChoice, WizardInstance, WizardStepProgress.

Generated to match NetBox v4.5.9's NetBoxModel base (see
netbox/netbox/models/features.py in the netbox-community/netbox repo at that
tag): concrete columns contributed by the mixins are `created`,
`last_updated`, `custom_field_data`, and the `tags` manager field.
"""

import django.db.models.deletion
import taggit.managers
import utilities.json
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contenttypes", "0002_remove_content_type_name"),
        ("extras", "0001_squashed"),
        ("core", "0001_squashed_0005"),
    ]

    operations = [
        migrations.CreateModel(
            name="WizardDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                ("name", models.CharField(max_length=200, unique=True)),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("data_path", models.CharField(blank=True, editable=False, max_length=1000)),
                ("auto_sync_enabled", models.BooleanField(default=False)),
                ("data_synced", models.DateTimeField(blank=True, editable=False, null=True)),
                (
                    "data_file",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="core.datafile",
                    ),
                ),
                (
                    "data_source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="core.datasource",
                    ),
                ),
                ("tags", taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag")),
            ],
            options={
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="WizardStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                ("key", models.CharField(blank=True, max_length=100)),
                ("order", models.PositiveIntegerField(default=0)),
                ("title", models.CharField(max_length=200)),
                ("instructions", models.TextField(blank=True)),
                ("link_url", models.CharField(blank=True, max_length=500)),
                ("link_text", models.CharField(blank=True, default="Open", max_length=100)),
                ("is_decision", models.BooleanField(default=False)),
                ("decision_question", models.CharField(blank=True, max_length=200)),
                (
                    "is_multi_choice",
                    models.BooleanField(
                        default=False,
                        help_text="If checked, the user picks from a list of choices when completing this step, "
                        "and the wizard branches to a different next step per choice.",
                    ),
                ),
                (
                    "multi_choice_question",
                    models.CharField(
                        blank=True,
                        default="",
                        max_length=200,
                        help_text="The prompt shown above the choice buttons, "
                        "e.g. 'What type of resource do you want to delete?'.",
                    ),
                ),
                (
                    "definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="steps",
                        to="netbox_wizards.wizarddefinition",
                    ),
                ),
                (
                    "next_step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
                (
                    "next_step_if_true",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
                (
                    "next_step_if_false",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
                ("tags", taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag")),
            ],
            options={
                "ordering": ("definition", "order", "pk"),
            },
        ),
        migrations.CreateModel(
            name="WizardStepImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "image",
                    models.ImageField(upload_to="netbox_wizards/steps/%Y/%m/"),
                ),
                ("caption", models.CharField(blank=True, max_length=200)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
            ],
            options={
                "ordering": ("order", "pk"),
            },
        ),
        migrations.CreateModel(
            name="WizardStepChoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=100)),
                ("label", models.CharField(max_length=200)),
                ("order", models.PositiveIntegerField(default=0)),
                (
                    "step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
                (
                    "next_step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
            ],
            options={
                "ordering": ("order", "pk"),
            },
        ),
        migrations.CreateModel(
            name="WizardInstance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True, null=True)),
                ("last_updated", models.DateTimeField(auto_now=True, null=True)),
                (
                    "custom_field_data",
                    models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("in_progress", "In progress"), ("completed", "Completed"), ("cancelled", "Cancelled")],
                        default="in_progress",
                        max_length=30,
                    ),
                ),
                ("object_id", models.PositiveBigIntegerField(blank=True, null=True)),
                ("completed", models.DateTimeField(blank=True, null=True)),
                ("note", models.TextField(blank=True)),
                (
                    "content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="contenttypes.contenttype",
                    ),
                ),
                (
                    "current_step",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
                (
                    "definition",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="instances",
                        to="netbox_wizards.wizarddefinition",
                    ),
                ),
                (
                    "started_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("tags", taggit.managers.TaggableManager(through="extras.TaggedItem", to="extras.Tag")),
            ],
            options={
                "ordering": ("-created",),
            },
        ),
        migrations.CreateModel(
            name="WizardStepProgress",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("decision", models.BooleanField(blank=True, null=True)),
                ("choice_key", models.CharField(blank=True, default="", max_length=100)),
                (
                    "completed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "instance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progress",
                        to="netbox_wizards.wizardinstance",
                    ),
                ),
                (
                    "step",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to="netbox_wizards.wizardstep",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="wizardstepprogress",
            constraint=models.UniqueConstraint(fields=("instance", "step"), name="wizards_unique_instance_step"),
        ),
        migrations.AddConstraint(
            model_name="wizardstep",
            constraint=models.UniqueConstraint(
                condition=models.Q(("key", ""), _negated=True),
                fields=("definition", "key"),
                name="wizards_unique_definition_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="wizardstepchoice",
            constraint=models.UniqueConstraint(fields=("step", "key"), name="wizards_unique_step_choice_key"),
        ),
    ]
