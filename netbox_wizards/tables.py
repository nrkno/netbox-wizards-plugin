import django_tables2 as tables
from netbox.tables import NetBoxTable, columns

from .models import WizardDefinition, WizardInstance, WizardStep

START_BUTTON = """
{% load helpers %}
{% if record.is_active %}
<form method="post" action="{% url 'plugins:netbox_wizards:wizarddefinition_start' pk=record.pk %}" style="display:inline">
  {% csrf_token %}
  <button type="submit" class="btn btn-sm btn-success" title="Start wizard">
    <i class="mdi mdi-play"></i>
  </button>
</form>
{% endif %}
"""


class WizardDefinitionTable(NetBoxTable):
    name = tables.Column(linkify=True)
    is_active = columns.BooleanColumn()
    step_count = tables.Column(verbose_name="Steps", orderable=False)
    created = columns.DateTimeColumn()
    start = tables.TemplateColumn(
        template_code=START_BUTTON,
        verbose_name="",
        orderable=False,
    )

    class Meta(NetBoxTable.Meta):
        model = WizardDefinition
        fields = ("pk", "id", "name", "description", "is_active", "step_count", "created", "start")
        default_columns = ("name", "description", "is_active", "step_count", "start")


class WizardStepTable(NetBoxTable):
    order = tables.Column()
    title = tables.Column(linkify=True)
    key = tables.Column()
    is_decision = columns.BooleanColumn(verbose_name="Decision?")

    class Meta(NetBoxTable.Meta):
        model = WizardStep
        fields = ("pk", "id", "order", "title", "key", "is_decision", "link_url")
        default_columns = ("order", "title", "key", "is_decision")


class WizardInstanceTable(NetBoxTable):
    definition = tables.Column(linkify=True)
    status = columns.ChoiceFieldColumn()
    current_step = tables.Column(verbose_name="Current step")
    related_object = tables.Column(linkify=True, orderable=False)
    progress_percent = tables.Column(verbose_name="Progress", orderable=False)
    created = columns.DateTimeColumn()

    class Meta(NetBoxTable.Meta):
        model = WizardInstance
        fields = (
            "id",
            "definition",
            "status",
            "current_step",
            "related_object",
            "progress_percent",
            "started_by",
            "created",
            "completed",
        )
        default_columns = ("definition", "status", "current_step", "progress_percent", "started_by", "created")
        actions = ()
