"""
Middleware that injects a small floating progress widget near the end of
every HTML page, for any authenticated user with an active (in_progress)
WizardInstance. Registered via `PluginConfig.middleware`, so no manual
Django settings changes are needed to enable it.
"""

from django.template.loader import render_to_string


class WizardWidgetMiddleware:
    """Appends the wizard progress widget just before </body> on HTML responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if self._should_inject(request, response):
            widget_html = self._render_widget(request)
            if widget_html:
                response.content = response.content.replace(b"</body>", widget_html + b"</body>", 1)
                if response.get("Content-Length") is not None:
                    response["Content-Length"] = len(response.content)

        return response

    def _should_inject(self, request, response):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        content_type = response.get("Content-Type", "")
        if not content_type.startswith("text/html"):
            return False
        return b"</body>" in response.content

    def _render_widget(self, request):
        # Imported here to avoid a hard app-loading-order dependency at module import time.
        from .helpers import get_active_instances_for_user

        instances = get_active_instances_for_user(request.user)
        if not instances:
            return None

        html = render_to_string(
            "netbox_wizards/_widget.html",
            {"instances": instances, "instance": instances[0]},
            request=request,
        )
        return html.encode("utf-8")
