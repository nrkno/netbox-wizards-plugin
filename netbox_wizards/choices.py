"""Choice definitions for the netbox_wizards plugin."""


class WizardInstanceStatusChoices:
    """Status values for a WizardInstance (one user's run through a WizardDefinition)."""

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    CHOICES = (
        (STATUS_IN_PROGRESS, "In progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    )

    COLORS = {
        STATUS_IN_PROGRESS: "blue",
        STATUS_COMPLETED: "green",
        STATUS_CANCELLED: "gray",
    }
