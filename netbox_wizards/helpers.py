"""
Small wizard "engine": functions for starting, advancing, and cancelling a
user's run (WizardInstance) through a WizardDefinition's ordered steps.

These are used by the plugin's own views (Start/Continue/Cancel buttons), but
are also safe to call from other code (e.g. a NetBox Script) if a process
should kick off a guided wizard instead of doing everything itself.
"""

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .choices import WizardInstanceStatusChoices
from .models import WizardInstance, WizardStepProgress


def start_wizard(definition, *, user=None, related_object=None):
    """Create a new WizardInstance for `definition`, positioned at its first step."""
    first_step = definition.steps.order_by("order", "pk").first()

    instance = WizardInstance(
        definition=definition,
        current_step=first_step,
        started_by=user,
    )
    if related_object is not None:
        instance.content_type = ContentType.objects.get_for_model(related_object)
        instance.object_id = related_object.pk
    instance.full_clean()
    instance.save()
    return instance


def get_active_instance_for_user(user):
    """Return the user's most recently-started in-progress WizardInstance, if any."""
    if not user or not user.is_authenticated:
        return None
    return (
        WizardInstance.objects.filter(status=WizardInstanceStatusChoices.STATUS_IN_PROGRESS, started_by=user)
        .order_by("-created")
        .first()
    )


def get_active_instances_for_user(user):
    """Return all in-progress WizardInstances for a user, most recent first."""
    if not user or not user.is_authenticated:
        return []
    return list(
        WizardInstance.objects.filter(status=WizardInstanceStatusChoices.STATUS_IN_PROGRESS, started_by=user)
        .select_related("definition", "current_step")
        .prefetch_related("current_step__choices")
        .order_by("-created")
    )


def advance_wizard(instance, *, user=None, decision=None, choice=None):
    """
    Mark the instance's current step complete and move to the step it's
    configured to lead to next -- or mark the whole instance completed if
    that step doesn't specify a next step (decision steps branch based on
    `decision`; multi-choice steps branch on `choice`; other steps use
    their `next_step`).
    """
    current = instance.current_step

    if current is not None:
        WizardStepProgress.objects.update_or_create(
            instance=instance,
            step=current,
            defaults={
                "completed": True,
                "completed_at": timezone.now(),
                "completed_by": user,
                "decision": decision,
                "choice_key": choice or "",
            },
        )
        next_step = current.get_next_step(decision=decision, choice=choice)
    else:
        next_step = None

    if next_step is not None:
        instance.current_step = next_step
        instance.save()
    else:
        instance.mark_complete()

    return instance


def cancel_wizard(instance, *, note=""):
    """Cancel an in-progress wizard instance; it will never be completed."""
    if note:
        instance.note = note
    instance.cancel()
    return instance
