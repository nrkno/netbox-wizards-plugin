from netbox.api.serializers import NetBoxModelSerializer
from rest_framework import serializers

from ..helpers import get_stored_answers
from ..models import (
    MAX_ANSWER_LENGTH,
    WizardDefinition,
    WizardInstance,
    WizardStep,
    WizardStepChoice,
)


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
        fields = ("id", "key", "label", "answer_value", "order", "next_step")


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
            "is_text_input",
            "answer_key",
            "text_input_prompt",
            "text_input_placeholder",
            "text_input_help",
            "text_input_required",
            "text_input_regex",
            "text_input_validation_message",
            "choices",
        )
        brief_fields = ("id", "url", "display", "title", "order")


class WizardInstanceSerializer(NetBoxModelSerializer):
    answers = serializers.SerializerMethodField()

    def get_answers(self, instance):
        return get_stored_answers(instance)

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
            "answers",
        )
        brief_fields = ("id", "url", "display", "definition", "status")


class WizardAdvanceSerializer(serializers.Serializer):
    decision = serializers.BooleanField(required=False)
    choice = serializers.CharField(required=False)
    answer = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=False,
        max_length=MAX_ANSWER_LENGTH,
    )
