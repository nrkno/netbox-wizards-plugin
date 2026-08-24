from netbox.choices import ButtonColorChoices
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

wizard_definitions_item = PluginMenuItem(
    link="plugins:netbox_wizards:wizarddefinition_list",
    link_text="Wizard Library",
    permissions=["netbox_wizards.view_wizarddefinition"],
    buttons=(
        PluginMenuButton(
            link="plugins:netbox_wizards:wizarddefinition_add",
            title="Add",
            icon_class="mdi mdi-plus-thick",
            color=ButtonColorChoices.GREEN,
            permissions=["netbox_wizards.add_wizarddefinition"],
        ),
    ),
)

wizard_instances_item = PluginMenuItem(
    link="plugins:netbox_wizards:wizardinstance_list",
    link_text="Wizard Runs",
    permissions=["netbox_wizards.view_wizardinstance"],
)

menu = PluginMenu(
    label="Wizards",
    groups=(("Wizards", (wizard_definitions_item, wizard_instances_item)),),
    icon_class="mdi mdi-wizard-hat",
)
