"""
Auto-discover wizard definition YAML files in the DataSource and create
WizardDefinitions for them. Runs on plugin startup and after every
DataSource sync (via the post_sync signal).

Only creates new definitions or links unlinked ones — never re-syncs
existing linked definitions. NetBox's built-in auto_sync mechanism
handles ongoing updates for definitions with auto_sync_enabled=True.
"""

import logging

from django.db import OperationalError, ProgrammingError
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _on_datasource_synced(sender, instance, **kwargs):
    autolink_wizard_definitions()


def connect_post_sync_signal():
    from core.signals import post_sync

    post_sync.connect(_on_datasource_synced)


def autolink_wizard_definitions():
    try:
        _autolink()
    except (OperationalError, ProgrammingError):
        pass
    except Exception:
        logger.exception("Failed to auto-link wizard definitions from DataSource.")


def _autolink():
    from core.models import DataFile
    from django.utils.text import slugify

    from .models import WizardDefinition

    yaml_files = DataFile.objects.filter(path__regex=r"^wizard-definitions/[^/]+\.yaml$")
    if not yaml_files.exists():
        return

    linked_file_ids = set(
        WizardDefinition.objects.filter(data_file__in=yaml_files)
        .values_list("data_file_id", flat=True)
    )

    for data_file in yaml_files:
        if data_file.pk in linked_file_ids:
            continue

        try:
            data = data_file.get_data()
            if not isinstance(data, dict) or not data.get("name"):
                continue

            slug = data.get("slug") or slugify(data["name"])
            definition, created = WizardDefinition.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": data["name"],
                    "data_file": data_file,
                    "data_source": data_file.source,
                    "data_path": data_file.path,
                    "auto_sync_enabled": True,
                },
            )

            if created:
                definition.sync()
                definition.save()
                logger.info("Auto-created wizard definition '%s' from %s.", definition.name, data_file.path)
            elif not definition.data_file_id:
                definition.data_file = data_file
                definition.data_source = data_file.source
                definition.data_path = data_file.path
                definition.auto_sync_enabled = True
                definition.sync()
                definition.save()
                logger.info("Linked existing wizard definition '%s' to %s.", definition.name, data_file.path)

        except Exception:
            logger.exception("Failed to auto-link wizard definition from %s.", data_file.path)
