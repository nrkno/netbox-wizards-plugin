from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ..models import WizardDefinition, WizardInstance, WizardStep, WizardStepChoice


class WizardDefinitionSerializer(NetBoxModelSerializer):
    class Meta:
        model = WizardDefinition
        fields = (
            "id",
            "url",
            "display",
            "name",
            "slug",
            "description",
            "is_active",
            "step_count",
            "data_source",
            "data_file",
            "data_path",
            "auto_sync_enabled",
            "data_synced",
        )
        brief_fields = ("id", "url", "display", "name", "is_active")


class WizardStepChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WizardStepChoice
        fields = ("id", "key", "label", "order", "next_step")


class WizardStepSerializer(NetBoxModelSerializer):
    choices = WizardStepChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = WizardStep
        fields = (
            "id",
            "url",
            "display",
            "definition",
            "key",
            "order",
            "title",
            "instructions",
            "link_url",
            "link_text",
            "next_step",
            "is_decision",
            "decision_question",
            "next_step_if_true",
            "next_step_if_false",
            "is_multi_choice",
            "multi_choice_question",
            "choices",
        )
        brief_fields = ("id", "url", "display", "title", "order")


class WizardInstanceSerializer(NetBoxModelSerializer):
    class Meta:
        model = WizardInstance
        fields = (
            "id",
            "url",
            "display",
            "definition",
            "status",
            "current_step",
            "content_type",
            "object_id",
            "started_by",
            "created",
            "completed",
            "note",
        )
        brief_fields = ("id", "url", "display", "definition", "status")
