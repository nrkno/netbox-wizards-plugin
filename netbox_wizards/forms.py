from core.forms.mixins import SyncedDataMixin
from django import forms
from netbox.forms import NetBoxModelFilterSetForm, NetBoxModelForm
from utilities.forms.rendering import FieldSet

from .choices import WizardInstanceStatusChoices
from .models import WizardDefinition, WizardInstance, WizardStep, WizardStepChoice, WizardStepImage

WizardStepImageFormSet = forms.inlineformset_factory(
    WizardStep,
    WizardStepImage,
    fields=("image", "caption", "order"),
    extra=1,
    can_delete=True,
)

WizardStepChoiceFormSet = forms.inlineformset_factory(
    WizardStep,
    WizardStepChoice,
    fk_name="step",
    fields=("key", "label", "order", "next_step"),
    extra=2,
    can_delete=True,
)


class WizardDefinitionForm(SyncedDataMixin, NetBoxModelForm):
    fieldsets = (
        FieldSet("name", "slug", "description", "is_active", "tags", name="Wizard"),
        FieldSet("data_source", "data_file", "auto_sync_enabled", name="Data Source"),
    )

    class Meta:
        model = WizardDefinition
        fields = ("name", "slug", "description", "is_active", "tags", "data_source", "data_file", "auto_sync_enabled")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Once a definition is populated from a data file, its name/description/
        # is_active are overwritten on every sync -- editing them locally would
        # just be discarded, so make that clear rather than letting it happen silently.
        if self.instance.data_file_id:
            for field_name in ("name", "slug", "description", "is_active"):
                self.fields[field_name].disabled = True
            self.fields["name"].help_text = "Populated from the linked data file. Edit the source file instead."


class WizardStepForm(NetBoxModelForm):
    class Meta:
        model = WizardStep
        fields = (
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
            "tags",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Next-step targets must be another step within the same definition.
        definition_id = self.instance.definition_id or self.initial.get("definition") or self.data.get("definition")
        queryset = WizardStep.objects.all()
        if definition_id:
            queryset = queryset.filter(definition_id=definition_id)
        if self.instance.pk:
            queryset = queryset.exclude(pk=self.instance.pk)
        self.fields["next_step"].queryset = queryset
        self.fields["next_step_if_true"].queryset = queryset
        self.fields["next_step_if_false"].queryset = queryset


class WizardDefinitionFilterForm(NetBoxModelFilterSetForm):
    model = WizardDefinition

    name = forms.CharField(required=False)
    is_active = forms.NullBooleanField(required=False)


class WizardInstanceFilterForm(NetBoxModelFilterSetForm):
    model = WizardInstance

    definition = forms.ModelChoiceField(queryset=WizardDefinition.objects.all(), required=False)
    status = forms.MultipleChoiceField(choices=WizardInstanceStatusChoices.CHOICES, required=False)
