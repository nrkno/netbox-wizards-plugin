# netbox-wizards

A NetBox plugin providing a library of customizable, step-by-step guided wizards for multi-step NetBox processes.

## Features

- **Step-by-step wizards** — author ordered checklists with per-step instructions, links, and images to guide users through complex processes such as hardware onboarding, cabling, or decommissioning.
- **Decision and multi-choice branching** — steps can present a Yes/No decision prompt or a list of labelled choices that each route to a different part of the wizard.
- **Floating progress widget** — an always-visible overlay on every NetBox page shows the user's active wizard step and lets them resume from wherever they are in the UI.
- **DataSource sync** — wizard definitions can be authored as YAML files, version-controlled in a git repository, and synced into NetBox automatically via a NetBox DataSource.
- **REST API** — full CRUD access to definitions, steps, and instances, plus custom `advance` and `cancel` actions on instances.
- **Generic foreign key** — a wizard instance can optionally be linked to any NetBox object (device, rack, prefix, etc.) to give context for the task being performed.

## Compatibility

Developed and tested against **NetBox v4.5.9**. Requires **NetBox 4.4.0** or later. Python 3.10+.

## Installation

Install the package:

```bash
pip install netbox-wizards
```

Add the plugin to `PLUGINS` in your NetBox `configuration.py`:

```python
PLUGINS = [
    "netbox_wizards",
]
```

Apply the database migrations:

```bash
python manage.py migrate netbox_wizards
```

Restart the NetBox application server. The plugin registers its middleware
(`netbox_wizards.middleware.WizardWidgetMiddleware`) automatically via
`PluginConfig.middleware` — no additional configuration is needed.

## Quick Start

### Create a wizard definition in the UI

1. In NetBox, navigate to **Wizards → Wizard Library**.
2. Click **Add** and fill in the name, slug, and description.
3. Save the definition, then open it and click **Add step** to build the
   step sequence. Set the `order`, `title`, and `instructions` for each step.
   Use `next_step` to link steps together; leave it unset on the last step.

Wizard descriptions and instructions accept Markdown and inert formatting HTML,
but reject active HTML elements or attributes and executable link schemes. Step
links must use HTTP(S) or a root-relative NetBox path beginning with `/`.

### Start a wizard

On any wizard definition's detail page, click **Start wizard**. A new
`WizardInstance` is created for your user. If the wizard is relevant to a
specific NetBox object (for example a device being onboarded), you can link
the instance to that object when starting it, or edit the instance afterwards.

### Use the floating widget

Once you have an active instance the floating widget appears in the
bottom-right corner of every page. It shows the current step title and a
link to the active instance. Click **Advance** on the instance page to move
to the next step (answering any decision prompt or selecting a choice as
required), or click **Cancel** to abandon the instance.

## DataSource Sync

Wizard definitions can be managed as YAML files in a version-controlled
repository and synced into NetBox via a
[DataSource](https://docs.netbox.dev/en/stable/models/core/datasource/).

1. Author a YAML file following the schema described in
   [`examples/wizard-definitions/README.md`](examples/wizard-definitions/README.md).
2. Push the file to a git repository that NetBox has access to.
3. In NetBox, go to **Admin → Data Sources** and create or sync the DataSource.
4. Open (or create) a `WizardDefinition`, set **Data Source** and **File**,
   then click **Sync from data source**.

Enabling **Auto sync** on the definition causes it to re-sync automatically
whenever the DataSource is refreshed.

See the example files in [`examples/wizard-definitions/`](examples/wizard-definitions/)
for working YAML files that demonstrate linear flow, decision branching, and
multi-choice branching.

## REST API

Base URL: `/api/plugins/wizards/`

| Endpoint | Description |
|---|---|
| `GET /api/plugins/wizards/wizard-definitions/` | List all wizard definitions |
| `GET /api/plugins/wizards/wizard-definitions/{id}/` | Retrieve a definition |
| `POST /api/plugins/wizards/wizard-definitions/` | Create a definition |
| `PATCH /api/plugins/wizards/wizard-definitions/{id}/` | Update a definition |
| `DELETE /api/plugins/wizards/wizard-definitions/{id}/` | Delete a definition |
| `GET /api/plugins/wizards/wizard-steps/` | List all wizard steps |
| `GET /api/plugins/wizards/wizard-steps/{id}/` | Retrieve a step |
| `GET /api/plugins/wizards/wizard-instances/` | List all wizard instances |
| `GET /api/plugins/wizards/wizard-instances/{id}/` | Retrieve an instance |
| `POST /api/plugins/wizards/wizard-instances/` | Start a new instance |
| `DELETE /api/plugins/wizards/wizard-instances/{id}/` | Delete an instance |

### Custom actions on instances

**Advance** — move the instance to the next step:

```
POST /api/plugins/wizards/wizard-instances/{id}/advance/
```

Request body (all fields optional):

```json
{
  "decision": true,
  "choice": "rack"
}
```

Pass `decision` (`true` or `false`) for decision steps, or `choice` (a choice
key string) for multi-choice steps. Both fields are ignored on plain steps.

**Cancel** — mark the instance as cancelled:

```
POST /api/plugins/wizards/wizard-instances/{id}/cancel/
```

Request body (optional):

```json
{
  "note": "No longer needed."
}
```

Both actions return the updated instance serialization.

## License

Apache 2.0. See [LICENSE](LICENSE).
