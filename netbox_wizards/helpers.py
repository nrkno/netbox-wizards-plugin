"""
Small wizard "engine": functions for starting, advancing, and cancelling a
user's run (WizardInstance) through a WizardDefinition's ordered steps.

These are used by the plugin's own views (Start/Continue/Cancel buttons), but
are also safe to call from other code (e.g. a NetBox Script) if a process
should kick off a guided wizard instead of doing everything itself.
"""

import re
import secrets
from html.parser import HTMLParser

import regex
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone

from .choices import WizardInstanceStatusChoices
from .models import MAX_ANSWER_LENGTH, WizardInstance, WizardStepProgress

_REGEX_TIMEOUT_SECONDS = 0.05


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


_ANSWER_TOKEN = re.compile(r"\{\{\s*answers\.([A-Za-z][A-Za-z0-9_]*)\s*\}\}")


def _validate_answer(current, *, decision=None, choice=None, answer=None):
    if current.is_multi_choice:
        if not isinstance(choice, str) or not choice:
            raise ValidationError("A choice is required for this step.")
        try:
            selected = current.choices.get(key=choice)
        except current.choices.model.DoesNotExist as error:
            raise ValidationError("The selected choice is not valid for this step.") from error
        return selected.answer_value if selected.answer_value is not None else selected.key
    if current.is_decision:
        if not isinstance(decision, bool):
            raise ValidationError("A true or false decision is required for this step.")
        return None
    if current.is_text_input:
        if not isinstance(answer, str):
            raise ValidationError("A text answer is required for this step.")
        if len(answer) > MAX_ANSWER_LENGTH:
            raise ValidationError(
                f"Text answers cannot exceed {MAX_ANSWER_LENGTH} characters."
            )
        if current.text_input_required and not answer:
            raise ValidationError("A text answer is required for this step.")
        if not answer:
            return answer
        if current.text_input_regex:
            try:
                matches = regex.fullmatch(
                    current.text_input_regex,
                    answer,
                    timeout=_REGEX_TIMEOUT_SECONDS,
                )
            except TimeoutError as error:
                raise ValidationError(
                    "Answer validation timed out. Contact an administrator to correct this step's validation expression."
                ) from error
            except regex.error as error:
                raise ValidationError(
                    "This step has an invalid validation expression. Contact an administrator."
                ) from error
            if matches is None:
                raise ValidationError(
                    current.text_input_validation_message or "The answer is not in the required format."
                )
        return answer
    return None


def get_stored_answers(instance):
    """Return answer-key/value pairs captured on completed steps."""
    return {
        progress.step.answer_key: progress.answer_value
        for progress in instance.progress.filter(
            completed=True,
            answer_value__isnull=False,
        ).select_related("step").order_by("completed_at", "pk")
        if progress.step.answer_key
    }


class _TextNodeAnswerInterpolator(HTMLParser):
    """Replace placeholders in HTML text nodes while preserving all markup."""

    def __init__(self, replacements):
        super().__init__(convert_charrefs=False)
        self.replacements = replacements
        self.placeholder_pattern = re.compile("|".join(map(re.escape, replacements)))
        self.output = []

    def _restore_tokens(self, value):
        return self.placeholder_pattern.sub(
            lambda match: self.replacements[match.group(0)][1],
            value,
        )

    def handle_starttag(self, tag, attrs):
        self.output.append(self._restore_tokens(self.get_starttag_text()))

    def handle_startendtag(self, tag, attrs):
        self.output.append(self._restore_tokens(self.get_starttag_text()))

    def handle_endtag(self, tag):
        self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(
            self.placeholder_pattern.sub(
                lambda match: self.replacements[match.group(0)][0],
                data,
            )
        )

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def handle_comment(self, data):
        self.output.append(f"<!--{self._restore_tokens(data)}-->")

    def handle_decl(self, decl):
        self.output.append(f"<!{self._restore_tokens(decl)}>")

    def handle_pi(self, data):
        self.output.append(f"<?{self._restore_tokens(data)}>")

    def unknown_decl(self, data):
        self.output.append(f"<![{self._restore_tokens(data)}]>")


def render_step_instructions(instance, step):
    """
    Render instructions first, then insert escaped answers only into HTML text
    nodes. This lets authored Markdown wrap tokens (for example, with ``**``)
    while preventing answers from becoming Markdown or HTML structure.
    """
    from django.utils.html import escape
    from django.utils.safestring import mark_safe
    from netbox.config import get_config
    from utilities.html import clean_html
    from utilities.templatetags.builtins.filters import render_markdown

    answers = get_stored_answers(instance)
    replacements = {}
    nonce = secrets.token_hex(16)

    def replace(match):
        key = match.group(1)
        if key not in answers:
            return match.group(0)
        placeholder = f"WIZARDANSWERTOKEN{nonce}{len(replacements)}X"
        replacements[placeholder] = (escape(str(answers[key])), f"{{{{ answers.{key} }}}}")
        return placeholder

    source = _ANSWER_TOKEN.sub(replace, step.instructions)
    rendered = str(render_markdown(source))
    if not replacements:
        return mark_safe(rendered)

    parser = _TextNodeAnswerInterpolator(replacements)
    parser.feed(rendered)
    parser.close()
    rendered = "".join(parser.output)
    rendered = clean_html(rendered, get_config().ALLOWED_URL_SCHEMES)
    return mark_safe(rendered)


def advance_wizard(instance, *, user=None, decision=None, choice=None, answer=None):
    """
    Mark the instance's current step complete and move to the step it's
    configured to lead to next -- or mark the whole instance completed if
    that step doesn't specify a next step (decision steps branch based on
    `decision`; multi-choice steps branch on `choice`; other steps use
    their `next_step`).
    """
    current = instance.current_step

    if current is not None:
        answer_value = _validate_answer(current, decision=decision, choice=choice, answer=answer)
        WizardStepProgress.objects.update_or_create(
            instance=instance,
            step=current,
            defaults={
                "completed": True,
                "completed_at": timezone.now(),
                "completed_by": user,
                "decision": decision,
                "choice_key": choice or "",
                "answer_value": answer_value,
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
