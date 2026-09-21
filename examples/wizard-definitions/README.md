# Wizard definition YAML files

This folder contains example wizard definition files for the
[netbox-wizards](https://github.com/nrkno/netbox-wizards-plugin) plugin.
Each file defines a `WizardDefinition` — including its steps and branching
logic — in a portable YAML format that can be version-controlled and imported
into NetBox via a [DataSource](https://docs.netbox.dev/en/stable/models/core/datasource/)
instead of being built by hand in the UI.

## Importing via DataSource

1. Host your YAML files in a git repository (or any other source supported by
   NetBox's DataSource feature).
2. In NetBox, go to **Admin → Data Sources** and create a new DataSource pointing
   at your repository.
3. Sync the DataSource so NetBox fetches the files.
4. In NetBox, go to **Wizards → Wizard Library** and add (or edit) a
   `WizardDefinition`. Under **Data Source** select your DataSource and choose
   the corresponding YAML file under **File**. Optionally enable **Auto sync**
   so future changes are picked up automatically.
5. Click **Sync from data source** (or save the form — selecting a file triggers
   an initial sync automatically) to populate the wizard's name, description,
   and steps from the file.

## File schema

```yaml
name: "My wizard"
slug: "my-wizard"            # optional; derived from name if omitted
description: "..."           # optional; supports NetBox markdown
is_active: true              # optional; defaults to true
steps:
  - key: step-one            # required; unique within the file; stable identifier
    order: 10                # controls display order; the lowest order is the starting step
    title: "Do the first thing"
    instructions: "..."      # optional; supports NetBox markdown (links, bold, images)
    image: "images/step-one.png"  # optional; path relative to this YAML file
                                  # can also be a list: ["img1.png", "img2.png"]
    link_url: "/dcim/devices/"    # optional; absolute path or full URL
    link_text: "Open Devices"     # optional; label for the link button
    next_step: step-two      # optional; key of the next step; omit to end the wizard here

  # Text-input step — validates and stores a value for later instructions
  - key: step-two
    order: 20
    title: "Name the service"
    is_text_input: true
    answer_key: service_name
    text_input_prompt: "Service name"
    text_input_placeholder: "payments-api"
    text_input_help: "Use lowercase letters, numbers, and hyphens."
    text_input_required: true
    text_input_regex: "[a-z][a-z0-9-]+"
    text_input_validation_message: "Use a lowercase service name."
    next_step: step-three

  # Decision step — shows a Yes / No prompt to the user
  - key: step-three
    order: 30
    title: "Was that successful?"
    instructions: "Continue configuring {{ answers.service_name }}."
    is_decision: true
    decision_question: "Did the operation complete without errors?"
    next_step_if_true: step-four   # key of step to go to on "Yes"
    next_step_if_false: step-one    # key of step to go to on "No"; omit to end wizard

  # Multi-choice step — shows a list of labelled options
  - key: step-four
    order: 40
    title: "Select the next action"
    is_multi_choice: true
    answer_key: environment_suffix
    multi_choice_question: "What would you like to do next?"
    choices:
      - key: option-a
        label: "Option A"
        value: ""                 # explicitly store an empty suffix
        next_step: step-four-a   # key of next step for this choice
      - key: option-b
        label: "Option B"
        value: "-test"            # stored value may differ from routing key
        next_step: step-four-b
      - key: option-c
        label: "Option C"
        # next_step omitted → ends the wizard when this choice is selected
```

### Field reference

| Field | Where | Required | Notes |
|---|---|---|---|
| `name` | top-level | yes | Human-readable name; displayed in the wizard library |
| `slug` | top-level | no | URL-safe identifier; derived from `name` if omitted |
| `description` | top-level | no | Shown at the top of the wizard; supports markdown |
| `is_active` | top-level | no | Defaults to `true`; inactive wizards cannot be started |
| `steps` | top-level | no | List of step objects (see below) |
| `key` | step | yes | Stable string identifier; unique within the file; referenced by `next_step` etc. |
| `order` | step | yes | Integer; controls display order; lowest order is the starting step |
| `title` | step | yes | Short step heading shown to the user |
| `instructions` | step | no | Longer explanation; supports markdown |
| `image` | step | no | Path relative to this file, or a list of up to 2 paths |
| `link_url` | step | no | URL or absolute path the "Open" button links to |
| `link_text` | step | no | Label for the link button; defaults to "Open" |
| `next_step` | step | no | Key of the next step; omit to end the wizard here |
| `is_decision` | step | no | `true` to show a Yes/No decision prompt |
| `decision_question` | step | no | Question text displayed on the decision prompt |
| `next_step_if_true` | step | no | Key of the next step when the user answers "Yes" |
| `next_step_if_false` | step | no | Key of the next step when the user answers "No" |
| `is_multi_choice` | step | no | `true` to show a list of labelled choices |
| `multi_choice_question` | step | no | Question text displayed above the choices |
| `choices` | step | no | List of choice objects (see below) |
| `is_text_input` | step | no | `true` to show a text field; mutually exclusive with decision and multi-choice modes |
| `answer_key` | step | text: yes; otherwise no | Stable key used by later `{{ answers.key }}` tokens; letters, numbers, and underscores only |
| `text_input_prompt` | step | text: yes | Label displayed for the text field |
| `text_input_placeholder` | step | no | Placeholder displayed in the text field |
| `text_input_help` | step | no | Additional help displayed with the prompt |
| `text_input_required` | step | no | Defaults to `true`; when `false`, an empty answer is allowed |
| `text_input_regex` | step | no | Regular expression matched against the complete answer with a 50 ms timeout |
| `text_input_validation_message` | step | no | User-facing message for a regex mismatch |
| `key` | choice | yes | Stable string identifier; unique within the step |
| `label` | choice | no | Display label; defaults to the choice `key` |
| `value` | choice | no | Stored answer value; if omitted, defaults to the choice `key`. An explicit empty string is preserved |
| `next_step` | choice | no | Key of the step to go to when this choice is selected; omit to end wizard |

### Stored-answer interpolation

Use `{{ answers.<answer_key> }}` in a later step's `instructions`. This is a
restricted token replacement, not Django/Jinja template evaluation. Captured
values are inserted after Markdown rendering and escaped as literal text.
Formatting authored around a token, such as `**{{ answers.service_name }}**`,
is preserved, but tokens in structural positions such as link destinations
are not populated. A token whose answer has not been captured is left
unchanged so missing data remains obvious.

Text answers have a fixed maximum length of 2,000 characters.

## Examples in this folder

| File | What it demonstrates |
|---|---|
| `getting-started.yaml` | Simple linear flow (no branching) |
| `new-device-onboarding.yaml` | Yes/No decision branch (`is_decision`) |
| `decommission-resource.yaml` | Multi-choice entry point (`is_multi_choice`) with separate paths per choice |
