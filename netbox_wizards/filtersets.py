import django_filters
from django.db.models import Q
from netbox.filtersets import NetBoxModelFilterSet

from .choices import WizardInstanceStatusChoices
from .models import WizardDefinition, WizardInstance, WizardStep


class WizardDefinitionFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = WizardDefinition
        fields = ("id", "name", "slug", "is_active")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(name__icontains=value) | Q(description__icontains=value))


class WizardStepFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = WizardStep
        fields = ("id", "definition", "order", "title")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(title__icontains=value) | Q(instructions__icontains=value))


class WizardInstanceFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(choices=WizardInstanceStatusChoices.CHOICES)

    class Meta:
        model = WizardInstance
        fields = ("id", "definition", "status", "started_by", "current_step")

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(definition__name__icontains=value) | Q(note__icontains=value))
