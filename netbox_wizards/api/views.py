from django.core.exceptions import ValidationError as DjangoValidationError
from netbox.api.authentication import TokenPermissions
from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from ..helpers import advance_wizard, cancel_wizard
from ..models import WizardDefinition, WizardInstance, WizardStep
from .serializers import (
    WizardAdvanceSerializer,
    WizardDefinitionSerializer,
    WizardInstanceSerializer,
    WizardStepSerializer,
)


class WizardInstanceChangePermission(TokenPermissions):
    """Map custom POST actions to change permission instead of add permission."""

    perms_map = {
        **TokenPermissions.perms_map,
        "POST": ["%(app_label)s.change_%(model_name)s"],
    }


class WizardDefinitionViewSet(NetBoxModelViewSet):
    queryset = WizardDefinition.objects.all()
    serializer_class = WizardDefinitionSerializer


class WizardStepViewSet(NetBoxModelViewSet):
    queryset = WizardStep.objects.all()
    serializer_class = WizardStepSerializer


class WizardInstanceViewSet(NetBoxModelViewSet):
    """
    Standard CRUD plus `advance`/`cancel` actions, so an external system could
    in the future drive a wizard instance forward automatically (e.g. once
    network automation confirms a step's real-world condition is met).
    """

    queryset = WizardInstance.objects.all()
    serializer_class = WizardInstanceSerializer

    def get_permissions(self):
        if self.action in {"advance", "cancel"}:
            return [WizardInstanceChangePermission()]
        return super().get_permissions()

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.action in {"advance", "cancel"}:
            # BaseViewSet maps every POST to "add"; custom mutation actions
            # operate on existing objects and must instead be restricted by change.
            self.queryset = WizardInstance.objects.restrict(request.user, "change")

    @staticmethod
    def _require_view_permission(request, instance):
        if not WizardInstance.objects.restrict(request.user, "view").filter(pk=instance.pk).exists():
            raise PermissionDenied("View permission is required to return stored answers.")

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        instance = self.get_object()
        self._require_view_permission(request, instance)
        user = request.user if request.user.is_authenticated else None
        current_step = instance.current_step
        if current_step and current_step.is_text_input:
            input_data = {"answer": request.data.get("answer", "")}
        elif current_step and current_step.is_multi_choice:
            input_data = {"choice": request.data.get("choice")}
        elif current_step and current_step.is_decision:
            input_data = {"decision": request.data.get("decision")}
        else:
            input_data = {}
        input_serializer = WizardAdvanceSerializer(data=input_data)
        input_serializer.is_valid(raise_exception=True)
        try:
            advance_wizard(instance, user=user, **input_serializer.validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"detail": error.messages}) from error
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        instance = self.get_object()
        self._require_view_permission(request, instance)
        note = request.data.get("note", "")
        cancel_wizard(instance, note=note)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
