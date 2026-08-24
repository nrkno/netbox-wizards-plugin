from django.urls import include, path
from utilities.urls import get_model_urls

from . import views  # noqa: F401 -- import triggers @register_model_view registration

urlpatterns = [
    path("wizard-definitions/", include(get_model_urls("netbox_wizards", "wizarddefinition", detail=False))),
    path("wizard-definitions/<int:pk>/", include(get_model_urls("netbox_wizards", "wizarddefinition"))),
    path("wizard-steps/", include(get_model_urls("netbox_wizards", "wizardstep", detail=False))),
    path("wizard-steps/<int:pk>/", include(get_model_urls("netbox_wizards", "wizardstep"))),
    path("wizard-instances/", include(get_model_urls("netbox_wizards", "wizardinstance", detail=False))),
    path("wizard-instances/<int:pk>/", include(get_model_urls("netbox_wizards", "wizardinstance"))),
]
