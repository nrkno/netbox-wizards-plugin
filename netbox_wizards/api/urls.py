from netbox.api.routers import NetBoxRouter

from .views import WizardDefinitionViewSet, WizardInstanceViewSet, WizardStepViewSet

router = NetBoxRouter()
router.register("wizard-definitions", WizardDefinitionViewSet)
router.register("wizard-steps", WizardStepViewSet)
router.register("wizard-instances", WizardInstanceViewSet)

urlpatterns = router.urls
