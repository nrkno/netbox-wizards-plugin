from netbox.plugins import PluginConfig


class NetboxWizardsConfig(PluginConfig):
    """PluginConfig for the NetBox Wizards plugin."""

    name = "netbox_wizards"
    verbose_name = "NetBox Wizards"
    description = (
        "A library of customizable, step-by-step guided wizards for multi-step NetBox "
        "processes (e.g. hardware delivery, physical cabling, manual approvals). Each step "
        "can include instructions, links, and images; an always-visible progress widget "
        "lets users track and resume their active wizard from any page."
    )
    version = "0.1.0"
    author = "NRK"
    base_url = "wizards"
    min_version = "4.4.0"
    default_settings = {}
    required_settings = []
    middleware = ["netbox_wizards.middleware.WizardWidgetMiddleware"]

    def ready(self):
        super().ready()
        from .autolink import connect_post_sync_signal

        connect_post_sync_signal()


config = NetboxWizardsConfig
