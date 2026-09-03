from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from netbox.models import NetBoxModel
from netbox.models.features import SyncedDataMixin

from .choices import WizardInstanceStatusChoices
from .validators import validate_safe_link_url, validate_safe_markdown


class WizardDefinition(SyncedDataMixin, NetBoxModel):
    """
    A reusable, admin-authored, step-by-step checklist for a multi-step NetBox
    process (e.g. "Replace planned device", "Install MPO breakout cable").
    Each WizardDefinition has an ordered set of WizardSteps; users "start"
    a definition to create a WizardInstance that tracks their own progress
    through it.

    Inherits SyncedDataMixin so a definition (and its steps) can optionally be
    populated/kept in sync from a YAML/JSON file via a NetBox DataSource --
    see datasource.py -- letting "standard" wizards be version-controlled
    and imported instead of built by hand in the UI. This also gives the
    model NetBox's built-in "Sync" view/button for free (see
    netbox.models.features.register_models(), called automatically from
    PluginConfig.ready()).
    """

    name = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True)
    description = models.TextField(
        blank=True,
        help_text="Shown at the top of the wizard. Supports NetBox markdown (links, formatting).",
        validators=[validate_safe_markdown],
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive wizards can no longer be started, but existing instances are unaffected.",
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("plugins:netbox_wizards:wizarddefinition", args=[self.pk])

    @property
    def step_count(self):
        return self.steps.count()

    def sync_data(self):
        """
        Populate this definition's own fields from its assigned DataFile's
        YAML/JSON content. Per SyncedDataMixin's contract this must NOT save
        `self` -- so step data is only *staged* here; `save()` (below)
        applies it once this definition definitely has a primary key.
        """
        from . import datasource

        try:
            data = datasource.parse_definition_data(self.data_file.get_data())
        except ValidationError as error:
            raise self._data_file_validation_error(error) from error

        self.name = data.get("name") or self.name
        self.slug = data.get("slug") or self.slug or slugify(self.name)
        self.description = data.get("description", self.description)
        self.is_active = data.get("is_active", True)
        self._synced_data = data

    sync_data.alters_data = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        data = getattr(self, "_synced_data", None)
        if data is not None:
            from . import datasource

            try:
                datasource.apply_synced_definition(self, data, data_file=self.data_file)
            except ValidationError as error:
                raise self._data_file_validation_error(error) from error
            finally:
                del self._synced_data

    def _data_file_validation_error(self, error):
        path = self.data_file.path if self.data_file_id else self.data_path
        return ValidationError(
            f"Wizard definition file '{path or 'unknown'}': {'; '.join(error.messages)}"
        )


class WizardStep(NetBoxModel):
    """A single step within a WizardDefinition."""

    definition = models.ForeignKey(to=WizardDefinition, on_delete=models.CASCADE, related_name="steps")
    key = models.CharField(
        max_length=100,
        blank=True,
        help_text="Stable identifier for this step, unique within its definition. Used to reference this step "
        "from other steps' 'next step' when the wizard is defined/synced via a YAML/JSON data source file. "
        "Not needed for steps created directly in the UI.",
    )
    order = models.PositiveIntegerField(default=0, help_text="Determines the step's position in the wizard.")
    title = models.CharField(max_length=200)
    instructions = models.TextField(
        blank=True,
        help_text="What the user needs to do for this step. Supports NetBox markdown, including links.",
        validators=[validate_safe_markdown],
    )
    link_url = models.CharField(
        max_length=500,
        blank=True,
        help_text="Optional URL for this step, e.g. a NetBox Script, a NetBox object, or an external document.",
        validators=[validate_safe_link_url],
    )
    link_text = models.CharField(max_length=100, blank=True, default="Open")

    # The wizard is an explicit graph, not just a straight line through `order`:
    # every step says exactly what comes next (or that the wizard ends here).
    # `order` only affects how steps are listed/displayed and which step a new
    # instance starts on (the lowest `order`); it has no bearing on what happens
    # when a step is completed.
    next_step = models.ForeignKey(
        to="self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Step to continue to after this one (only used when this is not a decision step). "
        "Leave blank to end the wizard after this step.",
    )

    # Conditional branching: if is_decision is set, the user is asked a yes/no
    # question when completing this step, and `next_step` above is ignored --
    # the wizard instead branches to next_step_if_true/next_step_if_false
    # depending on the answer.
    is_decision = models.BooleanField(
        default=False,
        help_text="If checked, the user answers a yes/no question on this step, and the wizard "
        "branches to a different next step depending on the answer (instead of using 'Next step' above).",
    )
    decision_question = models.CharField(
        max_length=200,
        blank=True,
        help_text="The yes/no question shown to the user, e.g. 'Is the device already racked?'.",
    )
    next_step_if_true = models.ForeignKey(
        to="self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Step to continue to if the answer is Yes. Leave blank to end the wizard on Yes.",
    )
    next_step_if_false = models.ForeignKey(
        to="self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Step to continue to if the answer is No. Leave blank to end the wizard on No.",
    )

    # Multi-choice branching: if is_multi_choice is set, the user picks from a
    # list of WizardStepChoice options, each pointing to a different next step.
    # Mutually exclusive with is_decision.
    is_multi_choice = models.BooleanField(
        default=False,
        help_text="If checked, the user picks from a list of choices when completing this step, "
        "and the wizard branches to a different next step per choice.",
    )
    multi_choice_question = models.CharField(
        max_length=200,
        blank=True,
        help_text="The prompt shown above the choice buttons, e.g. 'What type of resource do you want to delete?'.",
    )

    class Meta:
        ordering = ("definition", "order", "pk")
        constraints = [
            models.UniqueConstraint(
                fields=("definition", "key"),
                condition=~models.Q(key=""),
                name="wizards_unique_definition_key",
            ),
        ]

    def __str__(self):
        return f"{self.definition}: {self.order}. {self.title}"

    def get_absolute_url(self):
        # Steps are managed inline from their parent definition's page.
        return self.definition.get_absolute_url()

    def clean(self):
        super().clean()
        if self.is_decision and self.is_multi_choice:
            raise ValidationError("A step cannot be both a yes/no decision and a multi-choice step.")
        for field_name in ("next_step", "next_step_if_true", "next_step_if_false"):
            target = getattr(self, field_name)
            if target is None:
                continue
            if target.definition_id != self.definition_id:
                raise ValidationError({field_name: "Must be a step within the same wizard definition."})
            if target.pk == self.pk:
                raise ValidationError({field_name: "A step cannot point to itself."})

    def get_next_step(self, decision=None, choice=None):
        """
        Resolve the next step to move to after this one, or None if the
        wizard ends here. Decision steps branch on `decision`; multi-choice
        steps branch on `choice` (a choice key string); other steps simply
        follow their configured `next_step`. There is no implicit fallback
        to the next step in `order` -- an unset target means the wizard
        ends at this step (for that branch, if applicable).
        """
        if self.is_multi_choice and choice is not None:
            try:
                return self.choices.get(key=choice).next_step
            except self.choices.model.DoesNotExist:
                return None
        if self.is_decision:
            return self.next_step_if_true if decision else self.next_step_if_false
        return self.next_step


class WizardInstance(NetBoxModel):
    """One user's active (or completed/cancelled) run through a WizardDefinition."""

    definition = models.ForeignKey(to=WizardDefinition, on_delete=models.PROTECT, related_name="instances")
    status = models.CharField(
        max_length=30,
        choices=WizardInstanceStatusChoices.CHOICES,
        default=WizardInstanceStatusChoices.STATUS_IN_PROGRESS,
    )
    current_step = models.ForeignKey(
        to=WizardStep, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # Optional generic FK to the NetBox object this run relates to (e.g. the device being replaced).
    content_type = models.ForeignKey(
        to=ContentType, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    related_object = GenericForeignKey(ct_field="content_type", fk_field="object_id")

    started_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    completed = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return f"{self.definition} ({self.get_status_display()})"

    def get_absolute_url(self):
        return reverse("plugins:netbox_wizards:wizardinstance", args=[self.pk])

    def get_status_color(self):
        return WizardInstanceStatusChoices.COLORS.get(self.status, "grey")

    @property
    def total_steps(self):
        return self.definition.steps.count()

    @property
    def completed_step_count(self):
        return self.progress.filter(completed=True).count()

    @property
    def progress_percent(self):
        # Once completed, always show 100% -- with branching, an instance's actual
        # path may not touch every step defined for the wizard, so the raw
        # completed/total ratio can undercount a finished run.
        if self.status == WizardInstanceStatusChoices.STATUS_COMPLETED:
            return 100
        total = self.total_steps
        if not total:
            return 0
        return min(round(self.completed_step_count / total * 100), 100)

    def is_step_completed(self, step):
        return self.progress.filter(step=step, completed=True).exists()

    def mark_complete(self):
        self.status = WizardInstanceStatusChoices.STATUS_COMPLETED
        self.current_step = None
        self.completed = timezone.now()
        self.save()

    def cancel(self):
        self.status = WizardInstanceStatusChoices.STATUS_CANCELLED
        self.completed = timezone.now()
        self.save()


class WizardStepImage(models.Model):
    """An image attached to a WizardStep, displayed in order."""

    step = models.ForeignKey(to=WizardStep, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="netbox_wizards/steps/%Y/%m/")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "pk")

    def __str__(self):
        return f"{self.step}: image {self.order}"


class WizardStepChoice(models.Model):
    """One option in a multi-choice wizard step. Selecting it advances the wizard to its configured next_step."""

    step = models.ForeignKey(to=WizardStep, on_delete=models.CASCADE, related_name="choices")
    key = models.CharField(max_length=100, help_text="Stable identifier, unique within the parent step.")
    label = models.CharField(max_length=200, help_text="Button text shown to the user.")
    order = models.PositiveIntegerField(default=0)
    next_step = models.ForeignKey(
        to=WizardStep,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Step to continue to when this choice is selected. Leave blank to end the wizard.",
    )

    class Meta:
        ordering = ("order", "pk")
        constraints = [
            models.UniqueConstraint(fields=("step", "key"), name="wizards_unique_step_choice_key"),
        ]

    def __str__(self):
        return f"{self.step}: {self.label}"

    def clean(self):
        super().clean()
        if self.next_step is not None:
            if self.next_step.definition_id != self.step.definition_id:
                raise ValidationError({"next_step": "Must be a step within the same wizard definition."})
            if self.next_step_id == self.step_id:
                raise ValidationError({"next_step": "A choice cannot point back to its own step."})


class WizardStepProgress(models.Model):
    """
    Tracks whether a given step has been completed within a specific
    WizardInstance. A plain (non-NetBoxModel) internal bookkeeping table --
    it isn't meant to be independently browsed/permissioned like the other
    models in this plugin.
    """

    instance = models.ForeignKey(to=WizardInstance, on_delete=models.CASCADE, related_name="progress")
    step = models.ForeignKey(to=WizardStep, on_delete=models.CASCADE, related_name="+")
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decision = models.BooleanField(
        null=True, blank=True, help_text="The yes/no answer given, if this was a decision step."
    )
    choice_key = models.CharField(
        max_length=100, blank=True, default="", help_text="The choice key selected, if this was a multi-choice step."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("instance", "step"), name="wizards_unique_instance_step"),
        ]

    def __str__(self):
        return f"{self.instance} / {self.step}"
