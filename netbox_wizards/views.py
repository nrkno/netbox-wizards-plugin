from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from .filtersets import WizardDefinitionFilterSet, WizardInstanceFilterSet
from .forms import (
    WizardDefinitionFilterForm,
    WizardDefinitionForm,
    WizardInstanceFilterForm,
    WizardStepChoiceFormSet,
    WizardStepForm,
    WizardStepImageFormSet,
)
from .helpers import advance_wizard, cancel_wizard, start_wizard
from .models import WizardDefinition, WizardInstance, WizardStep
from .tables import WizardDefinitionTable, WizardInstanceTable

#
# WizardDefinition
#


@register_model_view(WizardDefinition, name="list", path="", detail=False)
class WizardDefinitionListView(generic.ObjectListView):
    queryset = WizardDefinition.objects.all()
    table = WizardDefinitionTable
    filterset = WizardDefinitionFilterSet
    filterset_form = WizardDefinitionFilterForm


@register_model_view(WizardDefinition)
class WizardDefinitionView(generic.ObjectView):
    queryset = WizardDefinition.objects.all()


@register_model_view(WizardDefinition, name="steps", path="steps")
class WizardDefinitionStepsView(generic.ObjectView):
    queryset = WizardDefinition.objects.all()
    template_name = "netbox_wizards/wizarddefinition_steps.html"
    tab = ViewTab(
        label="Steps",
        badge=lambda obj: obj.steps.count(),
    )

    def get_extra_context(self, request, instance):
        return {"steps": instance.steps.order_by("order", "pk")}


@register_model_view(WizardDefinition, name="add", detail=False)
@register_model_view(WizardDefinition, name="edit")
class WizardDefinitionEditView(generic.ObjectEditView):
    queryset = WizardDefinition.objects.all()
    form = WizardDefinitionForm


@register_model_view(WizardDefinition, name="delete")
class WizardDefinitionDeleteView(generic.ObjectDeleteView):
    queryset = WizardDefinition.objects.all()


@register_model_view(WizardDefinition, name="start")
class WizardDefinitionStartView(PermissionRequiredMixin, View):
    """Start a new WizardInstance for this definition and jump straight into it."""

    permission_required = "netbox_wizards.add_wizardinstance"

    def post(self, request, pk):
        definition = get_object_or_404(WizardDefinition, pk=pk, is_active=True)
        instance = start_wizard(definition, user=request.user)
        messages.success(request, f"Started wizard: {definition}.")
        return redirect(instance.get_absolute_url())


#
# WizardStep (managed inline from the parent WizardDefinition's page)
#


@register_model_view(WizardStep, name="add", detail=False)
@register_model_view(WizardStep, name="edit")
class WizardStepEditView(generic.ObjectEditView):
    queryset = WizardStep.objects.all()
    form = WizardStepForm
    template_name = "netbox_wizards/wizardstep_edit.html"

    def _steps_tab_url(self, obj):
        if obj.definition_id:
            return obj.definition.get_absolute_url() + "steps/"
        return None

    def alter_object(self, obj, request, url_args, url_kwargs):
        if not obj.pk and (definition_id := request.GET.get("definition")):
            obj.definition_id = definition_id
        return obj

    def get_return_url(self, request, obj=None):
        if obj and (url := self._steps_tab_url(obj)):
            return url
        return super().get_return_url(request, obj)

    def get_extra_context(self, request, instance):
        ctx = super().get_extra_context(request, instance)
        if request.method == "POST":
            ctx["image_formset"] = WizardStepImageFormSet(
                request.POST, request.FILES, instance=instance, prefix="images"
            )
            ctx["choice_formset"] = WizardStepChoiceFormSet(
                request.POST, instance=instance, prefix="choices"
            )
        else:
            ctx["image_formset"] = WizardStepImageFormSet(instance=instance, prefix="images")
            ctx["choice_formset"] = WizardStepChoiceFormSet(instance=instance, prefix="choices")
        return ctx

    def post(self, request, *args, **kwargs):
        obj = self.get_object(**kwargs)
        obj = self.alter_object(obj, request, args, kwargs)
        form = self.form(data=request.POST, files=request.FILES, instance=obj)
        image_formset = WizardStepImageFormSet(
            request.POST, request.FILES, instance=obj, prefix="images"
        )
        choice_formset = WizardStepChoiceFormSet(
            request.POST, instance=obj, prefix="choices"
        )

        if form.is_valid() and image_formset.is_valid() and choice_formset.is_valid():
            with transaction.atomic():
                obj = form.save()
                image_formset.instance = obj
                image_formset.save()
                choice_formset.instance = obj
                choice_formset.save()
            msg = f'{"Created" if not kwargs.get("pk") else "Modified"} {obj}'
            messages.success(request, msg)
            return redirect(self.get_return_url(request, obj))

        return render(request, self.template_name, {
            "object": obj,
            "form": form,
            "image_formset": image_formset,
            "choice_formset": choice_formset,
            "return_url": self.get_return_url(request, obj),
        })


@register_model_view(WizardStep, name="delete")
class WizardStepDeleteView(generic.ObjectDeleteView):
    queryset = WizardStep.objects.all()

    def get_return_url(self, request, obj=None):
        if obj and obj.definition_id:
            return obj.definition.get_absolute_url() + "steps/"
        return super().get_return_url(request, obj)


#
# WizardInstance
#


@register_model_view(WizardInstance, name="list", path="", detail=False)
class WizardInstanceListView(generic.ObjectListView):
    queryset = WizardInstance.objects.all()
    table = WizardInstanceTable
    filterset = WizardInstanceFilterSet
    filterset_form = WizardInstanceFilterForm


@register_model_view(WizardInstance)
class WizardInstanceView(generic.ObjectView):
    queryset = WizardInstance.objects.all()

    def get_extra_context(self, request, instance):
        steps = list(instance.definition.steps.order_by("order", "pk"))
        return {
            "steps": steps,
            "completed_step_ids": set(instance.progress.filter(completed=True).values_list("step_id", flat=True)),
        }


@register_model_view(WizardInstance, name="edit")
class WizardInstanceEditView(generic.ObjectView):
    """Wizard instances are not editable — redirect to the detail view."""

    queryset = WizardInstance.objects.all()

    def get(self, request, pk):
        instance = get_object_or_404(WizardInstance, pk=pk)
        return redirect(instance.get_absolute_url())


@register_model_view(WizardInstance, name="delete")
class WizardInstanceDeleteView(generic.ObjectDeleteView):
    queryset = WizardInstance.objects.all()


@register_model_view(WizardInstance, name="advance")
class WizardInstanceAdvanceView(PermissionRequiredMixin, View):
    """Mark the instance's current step complete and move to the next one."""

    permission_required = "netbox_wizards.change_wizardinstance"

    def post(self, request, pk):
        instance = get_object_or_404(WizardInstance, pk=pk)
        current_step = instance.current_step
        return_url = request.POST.get("next") or instance.get_absolute_url()

        decision = None
        choice = None

        if current_step and current_step.is_multi_choice:
            choice = request.POST.get("choice")
            if not choice or not current_step.choices.filter(key=choice).exists():
                messages.error(request, "Please select an option before continuing.")
                return redirect(return_url)
        elif current_step and current_step.is_decision:
            raw_decision = request.POST.get("decision")
            if raw_decision not in ("true", "false"):
                messages.error(request, "Please answer the question before continuing.")
                return redirect(return_url)
            decision = raw_decision == "true"

        advance_wizard(instance, user=request.user, decision=decision, choice=choice)
        return redirect(return_url)


@register_model_view(WizardInstance, name="cancel")
class WizardInstanceCancelView(PermissionRequiredMixin, View):
    """Cancel a wizard instance that will never be completed."""

    permission_required = "netbox_wizards.change_wizardinstance"

    def post(self, request, pk):
        instance = get_object_or_404(WizardInstance, pk=pk)
        cancel_wizard(instance)
        messages.success(request, f"Cancelled wizard: {instance.definition}.")
        return_url = request.POST.get("next") or instance.get_absolute_url()
        return redirect(return_url)
