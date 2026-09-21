"""
Support for defining WizardDefinitions (and their steps) as YAML/JSON
files synced from a NetBox DataSource, so "standard"/canonical wizards can
be version-controlled and imported or updated from a git repository (or any
other configured DataSource) instead of being built by hand in the UI.

See ../../examples/wizard-definitions/ in this repository for a working example,
and the plugin's README.md for the full file schema.

Expected file structure::

    name: "My wizard"
    slug: "my-wizard"            # optional, derived from name if omitted
    description: "..."
    is_active: true
    steps:
      - key: step-one              # stable id, referenced by other steps' "next_step"
        order: 10
        title: "Do the first thing"
        instructions: "..."
        image: "images/step-one.png"  # path relative to this YAML file (string or list of up to 2)
        link_url: "https://..."
        link_text: "Open"
        next_step: step-two        # references another step's `key`
      - key: step-two
        order: 20
        title: "Do the second thing"
        is_decision: true
        decision_question: "Did it work?"
        next_step_if_true: step-one   # e.g. loop back and try again
        # next_step_if_false left unset -> ends the wizard on "No"

Notes:
  - The ``image`` field accepts a path relative to the YAML file's location
    within the DataSource. The referenced file must exist as a DataFile in
    the same DataSource (i.e. it must be synced alongside the YAML). If the
    image path cannot be resolved, the step's image is left unchanged and a
    warning is logged.
  - Every step must have a unique, non-empty `key` within the file. Steps are
    upserted by `key` on each sync; any existing step whose `key` is no
    longer present in the file is deleted (which cascades to its
    WizardStepProgress rows -- an accepted trade-off for keeping a
    definition's steps in sync with their canonical source).
"""

import logging
import posixpath

import regex
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from .validators import validate_safe_link_url, validate_safe_markdown

logger = logging.getLogger(__name__)

# Plain fields copied directly from each step's data. Defaults are applied on
# every sync so removing an optional YAML field restores the model default
# instead of retaining stale state from an earlier revision.
_STEP_FIELD_DEFAULTS = {
    "order": 0,
    "instructions": "",
    "link_url": "",
    "link_text": "Open",
    "is_decision": False,
    "decision_question": "",
    "is_multi_choice": False,
    "multi_choice_question": "",
    "is_text_input": False,
    "answer_key": "",
    "text_input_prompt": "",
    "text_input_placeholder": "",
    "text_input_help": "",
    "text_input_required": True,
    "text_input_regex": "",
    "text_input_validation_message": "",
}
# Fields that reference another step by its `key`, resolved once all steps exist.
_STEP_LINK_FIELDS = ("next_step", "next_step_if_true", "next_step_if_false")


def parse_definition_data(raw_data):
    """Validate the top-level structure of a wizard definition file's parsed content."""
    if not isinstance(raw_data, dict):
        raise ValidationError("Wizard definition file must contain a YAML/JSON mapping (object).")
    if not raw_data.get("name"):
        raise ValidationError("Wizard definition file must specify a 'name'.")
    _validate_source_field("Wizard description", validate_safe_markdown, raw_data.get("description", ""))

    steps_data = raw_data.get("steps") or []
    if not isinstance(steps_data, list):
        raise ValidationError("Wizard definition file's 'steps' must be a list.")
    _validate_steps_data(steps_data)

    return raw_data


def _validate_steps_data(steps_data):
    seen_keys = set()
    seen_answer_keys = set()
    for index, step_data in enumerate(steps_data):
        if not isinstance(step_data, dict):
            raise ValidationError(f"Step {index + 1} must be a mapping (object).")
        key = step_data.get("key")
        if not key:
            raise ValidationError(f"Step {index + 1} is missing a required 'key'.")
        if key in seen_keys:
            raise ValidationError(f"Duplicate step key '{key}'.")
        seen_keys.add(key)
        if not step_data.get("title"):
            raise ValidationError(f"Step '{key}' is missing a required 'title'.")
        modes = (
            bool(step_data.get("is_decision")),
            bool(step_data.get("is_multi_choice")),
            bool(step_data.get("is_text_input")),
        )
        if sum(modes) > 1:
            raise ValidationError(
                f"Step '{key}' can only use one of decision, multi-choice, or text-input mode."
            )
        answer_key = step_data.get("answer_key", "")
        if step_data.get("is_text_input") and not answer_key:
            raise ValidationError(f"Step '{key}' text-input mode requires 'answer_key'.")
        if step_data.get("is_text_input") and not step_data.get("text_input_prompt"):
            raise ValidationError(f"Step '{key}' text-input mode requires 'text_input_prompt'.")
        if answer_key:
            if not isinstance(answer_key, str) or not regex.fullmatch(
                r"[A-Za-z][A-Za-z0-9_]*",
                answer_key,
            ):
                raise ValidationError(f"Step '{key}' has an invalid 'answer_key'.")
            if answer_key in seen_answer_keys:
                raise ValidationError(f"Duplicate answer key '{answer_key}'.")
            seen_answer_keys.add(answer_key)
        validation_regex = step_data.get("text_input_regex", "")
        if validation_regex:
            try:
                regex.compile(validation_regex)
            except (regex.error, TypeError) as error:
                raise ValidationError(
                    f"Step '{key}' has an invalid 'text_input_regex': {error}."
                ) from error
        _validate_source_field(
            f"Step '{key}' instructions",
            validate_safe_markdown,
            step_data.get("instructions", ""),
        )
        _validate_source_field(
            f"Step '{key}' link_url",
            validate_safe_link_url,
            step_data.get("link_url", ""),
        )

    for step_data in steps_data:
        for field in _STEP_LINK_FIELDS:
            target_key = step_data.get(field)
            if target_key and target_key not in seen_keys:
                raise ValidationError(
                    f"Step '{step_data['key']}' references unknown step '{target_key}' in '{field}'."
                )

        choices = step_data.get("choices")
        if choices:
            if not isinstance(choices, list):
                raise ValidationError(f"Step '{step_data['key']}' 'choices' must be a list.")
            if len(choices) < 2:
                raise ValidationError(f"Step '{step_data['key']}' must have at least 2 choices.")
            choice_keys = set()
            for ci, choice in enumerate(choices):
                if not isinstance(choice, dict):
                    raise ValidationError(f"Step '{step_data['key']}' choice {ci + 1} must be a mapping.")
                ckey = choice.get("key")
                if not ckey:
                    raise ValidationError(f"Step '{step_data['key']}' choice {ci + 1} is missing 'key'.")
                if ckey in choice_keys:
                    raise ValidationError(f"Step '{step_data['key']}' has duplicate choice key '{ckey}'.")
                choice_keys.add(ckey)
                if "value" in choice and not isinstance(choice["value"], str):
                    raise ValidationError(
                        f"Step '{step_data['key']}' choice '{ckey}' 'value' must be text."
                    )
                target = choice.get("next_step")
                if target and target not in seen_keys:
                    raise ValidationError(
                        f"Step '{step_data['key']}' choice '{ckey}' references unknown step '{target}'."
                    )


def _validate_source_field(field_label, validator, value):
    try:
        validator(value)
    except ValidationError as error:
        raise ValidationError(f"{field_label}: {'; '.join(error.messages)}") from error


@transaction.atomic
def apply_synced_definition(definition, data, *, data_file=None):
    """
    Replace `definition`'s steps to match `data["steps"]`. Called from
    WizardDefinition.save() once the definition itself has a primary key.
    """
    _sync_steps(definition, data.get("steps") or [], data_file=data_file)


def _resolve_image(image_path, data_file):
    """
    Resolve a relative image path against the YAML file's location in
    the DataSource and return (filename, ContentFile) or None.
    """
    if not data_file:
        return None

    from core.models import DataFile

    yaml_dir = posixpath.dirname(data_file.path)
    absolute_path = posixpath.normpath(posixpath.join(yaml_dir, image_path))

    try:
        image_file = DataFile.objects.get(source=data_file.source, path=absolute_path)
    except DataFile.DoesNotExist:
        logger.warning(
            "Wizard sync: image '%s' (resolved to '%s') not found in DataSource '%s'.",
            image_path,
            absolute_path,
            data_file.source,
        )
        return None

    filename = posixpath.basename(absolute_path)
    return filename, ContentFile(image_file.data, name=filename)


def _sync_step_images(step, raw_images, data_file):
    """Replace a step's images with those listed in the YAML (string or list)."""
    from .models import WizardStepImage

    paths = raw_images if isinstance(raw_images, list) else [raw_images] if raw_images else []
    step.images.all().delete()

    for order, image_path in enumerate(paths):
        if not image_path:
            continue
        result = _resolve_image(image_path, data_file)
        if result:
            filename, content = result
            img = WizardStepImage(step=step, order=order, caption="")
            img.image.save(filename, content, save=False)
            img.save()


def _sync_step_choices(step, choices_data, steps_by_key):
    """Replace a step's choices with those listed in the YAML."""
    from .models import WizardStepChoice

    step.choices.all().delete()
    for order, choice_data in enumerate(choices_data):
        target_key = choice_data.get("next_step")
        target = steps_by_key.get(target_key) if target_key else None
        choice = WizardStepChoice(
            step=step,
            key=choice_data["key"],
            label=choice_data.get("label", choice_data["key"]),
            answer_value=choice_data.get("value"),
            order=order,
            next_step=target,
        )
        choice.full_clean()
        choice.save()


def _sync_steps(definition, steps_data, *, data_file=None):
    from .models import WizardStep

    existing_by_key = {step.key: step for step in definition.steps.exclude(key="")}
    seen_keys = set()
    steps_by_key = {}

    # Clear answer keys which are changing before assigning any new values.
    # This permits atomic swaps under the conditional uniqueness constraint.
    incoming_answer_keys = {
        step_data["key"]: step_data.get("answer_key", "")
        for step_data in steps_data
    }
    for key, step in existing_by_key.items():
        if step.answer_key and step.answer_key != incoming_answer_keys.get(key, ""):
            step.answer_key = ""
            step.save(update_fields=("answer_key",))

    # First pass: create/update each step's plain fields. Link fields are
    # resolved afterwards, once every step referenced by `key` exists.
    for step_data in steps_data:
        key = step_data["key"]
        seen_keys.add(key)
        step = existing_by_key.get(key) or WizardStep(definition=definition, key=key)
        step.title = step_data["title"]
        for field, default in _STEP_FIELD_DEFAULTS.items():
            setattr(step, field, step_data.get(field, default))

        step.full_clean()
        step.save()

        if "image" in step_data:
            _sync_step_images(step, step_data["image"], data_file)
        steps_by_key[key] = step

    # Second pass: resolve next-step links now that all steps exist.
    for step_data in steps_data:
        step = steps_by_key[step_data["key"]]
        changed = False
        for field in _STEP_LINK_FIELDS:
            target_key = step_data.get(field)
            target = steps_by_key.get(target_key) if target_key else None
            if getattr(step, f"{field}_id") != (target.pk if target else None):
                setattr(step, field, target)
                changed = True
        if changed:
            step.full_clean()
            step.save()

    # Third pass: sync choices for multi-choice steps.
    for step_data in steps_data:
        step = steps_by_key[step_data["key"]]
        if step_data.get("choices"):
            _sync_step_choices(step, step_data["choices"], steps_by_key)
        elif step.choices.exists():
            step.choices.all().delete()

    # Remove steps no longer present in the source file.
    for key, step in existing_by_key.items():
        if key not in seen_keys:
            step.delete()
