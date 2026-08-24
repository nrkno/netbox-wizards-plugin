from netbox.api.viewsets import NetBoxModelViewSet
from rest_framework.decorators import action
from rest_framework.response import Response

from ..helpers import advance_wizard, cancel_wizard
from ..models import WizardDefinition, WizardInstance, WizardStep
from .serializers import WizardDefinitionSerializer, WizardInstanceSerializer, WizardStepSerializer


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

    @action(detail=True, methods=["post"])
    def advance(self, request, pk=None):
        instance = self.get_object()
        user = request.user if request.user.is_authenticated else None
        decision = request.data.get("decision")
        if isinstance(decision, str):
            decision = decision.lower() == "true"
        choice = request.data.get("choice")
        advance_wizard(instance, user=user, decision=decision, choice=choice)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        instance = self.get_object()
        note = request.data.get("note", "")
        cancel_wizard(instance, note=note)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
