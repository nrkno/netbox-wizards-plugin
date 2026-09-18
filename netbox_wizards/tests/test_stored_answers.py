from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from netbox_wizards.api.serializers import WizardInstanceSerializer
from netbox_wizards.api.views import WizardInstanceViewSet
from netbox_wizards.datasource import apply_synced_definition, parse_definition_data
from netbox_wizards.forms import WizardStepChoiceForm
from netbox_wizards.helpers import (
    advance_wizard,
    render_step_instructions,
    start_wizard,
)
from netbox_wizards.models import (
    MAX_ANSWER_LENGTH,
    WizardDefinition,
    WizardStep,
    WizardStepChoice,
    WizardStepProgress,
)
from netbox_wizards.views import WizardInstanceAdvanceView


class StoredAnswerTestCase(TestCase):
    def setUp(self):
        self.definition = WizardDefinition.objects.create(name="Service", slug="service")
        self.finish = WizardStep.objects.create(
            definition=self.definition,
            key="finish",
            order=20,
            title="Finish",
            instructions="Deploy `{{ answers.service_name }}`.",
        )
        self.input_step = WizardStep.objects.create(
            definition=self.definition,
            key="name",
            order=10,
            title="Name",
            next_step=self.finish,
            is_text_input=True,
            answer_key="service_name",
            text_input_prompt="Service name",
            text_input_required=True,
            text_input_regex=r"[a-z][a-z0-9-]+",
            text_input_validation_message="Use a lowercase service name.",
        )

    def test_text_mode_is_mutually_exclusive_and_requires_valid_configuration(self):
        self.input_step.is_decision = True
        with self.assertRaisesRegex(ValidationError, "only use one"):
            self.input_step.full_clean()

        self.input_step.is_decision = False
        self.input_step.answer_key = "not-a-token"
        with self.assertRaisesRegex(ValidationError, "letters, numbers"):
            self.input_step.full_clean()

        self.input_step.answer_key = "service_name"
        self.input_step.text_input_regex = "["
        with self.assertRaisesRegex(ValidationError, "Invalid regular expression"):
            self.input_step.full_clean()

    def test_text_answer_is_validated_persisted_and_interpolated_as_literal_text(self):
        instance = start_wizard(self.definition)
        with self.assertRaisesRegex(ValidationError, "lowercase service"):
            advance_wizard(instance, answer="INVALID")

        value = "<script>alert(1)</script> **not bold** ~~not struck~~"
        self.input_step.text_input_regex = ""
        self.input_step.save()
        advance_wizard(instance, answer=value)

        progress = WizardStepProgress.objects.get(instance=instance, step=self.input_step)
        self.assertEqual(progress.answer_value, value)
        rendered = render_step_instructions(instance, self.finish)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("**not bold**", rendered)
        self.assertIn("~~not struck~~", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("<strong>not bold</strong>", rendered)
        self.assertNotIn("<del>not struck</del>", rendered)

    def test_missing_answer_token_remains_identifiable(self):
        instance = start_wizard(self.definition)
        self.assertIn("{{ answers.service_name }}", render_step_instructions(instance, self.finish))

    def test_answer_cannot_create_markdown_structure_or_link_destination(self):
        self.input_step.text_input_regex = ""
        self.input_step.save()
        instance = start_wizard(self.definition)
        advance_wizard(instance, answer="javascript:alert(1)\n# heading\n| a | b |")

        self.finish.instructions = (
            "[unsafe]({{ answers.service_name }})\n\n"
            "{{ answers.service_name }}"
        )
        rendered = render_step_instructions(instance, self.finish)

        self.assertNotRegex(rendered, r'href="[^"]*javascript')
        self.assertNotIn("<h1>", rendered)
        self.assertNotIn("<table>", rendered)
        self.assertIn("# heading", rendered)

    def test_quoted_greater_than_attribute_never_receives_answer(self):
        self.input_step.text_input_regex = ""
        self.input_step.save()
        instance = start_wizard(self.definition)
        advance_wizard(instance, answer="INJECTED")
        self.finish.instructions = (
            '<span title="before > {{ answers.service_name }}">safe</span> '
            "{{ answers.service_name }}"
        )

        rendered = render_step_instructions(instance, self.finish)

        self.assertEqual(rendered.count("INJECTED"), 1)
        self.assertIn(">safe</span>", rendered)

    def test_token_inside_static_bold_markup_remains_bold(self):
        self.input_step.text_input_regex = ""
        self.input_step.save()
        instance = start_wizard(self.definition)
        advance_wizard(instance, answer="payments")
        self.finish.instructions = "**{{ answers.service_name }}.nrk.no**"

        rendered = render_step_instructions(instance, self.finish)

        self.assertIn("<strong>payments.nrk.no</strong>", rendered)

    def test_choice_value_can_be_distinct_or_intentionally_empty(self):
        choice_step = WizardStep.objects.create(
            definition=self.definition,
            key="environment",
            order=5,
            title="Environment",
            is_multi_choice=True,
            multi_choice_question="Environment?",
            answer_key="environment_suffix",
        )
        WizardStepChoice.objects.create(
            step=choice_step,
            key="production",
            label="Production",
            answer_value="",
        )
        WizardStepChoice.objects.create(step=choice_step, key="test", label="Test")

        production = start_wizard(self.definition)
        advance_wizard(production, choice="production")
        self.assertEqual(
            WizardStepProgress.objects.get(instance=production, step=choice_step).answer_value,
            "",
        )

        test = start_wizard(self.definition)
        advance_wizard(test, choice="test")
        self.assertEqual(
            WizardStepProgress.objects.get(instance=test, step=choice_step).answer_value,
            "test",
        )

    def test_later_instructions_combine_text_and_choice_answers(self):
        environment = WizardStep.objects.create(
            definition=self.definition,
            key="environment",
            order=15,
            title="Environment",
            next_step=self.finish,
            is_multi_choice=True,
            multi_choice_question="Environment?",
            answer_key="environment_suffix",
        )
        WizardStepChoice.objects.create(
            step=environment,
            key="production",
            label="Production",
            answer_value="",
            next_step=self.finish,
        )
        self.input_step.next_step = environment
        self.input_step.save()
        self.finish.instructions = (
            "Deploy {{ answers.service_name }}{{ answers.environment_suffix }}."
        )
        self.finish.save()

        instance = start_wizard(self.definition)
        advance_wizard(instance, answer="payments")
        advance_wizard(instance, choice="production")

        self.assertIn("Deploy payments.", render_step_instructions(instance, self.finish))

    def test_plain_and_decision_steps_remain_supported(self):
        plain = WizardStep(
            definition=self.definition,
            key="plain",
            title="Plain",
        )
        plain.full_clean()
        decision = WizardStep(
            definition=self.definition,
            key="decision",
            title="Decision",
            is_decision=True,
            decision_question="Continue?",
        )
        decision.full_clean()

    def test_answer_length_is_enforced_by_helper_and_model(self):
        instance = start_wizard(self.definition)
        oversized = "a" * (MAX_ANSWER_LENGTH + 1)

        with self.assertRaisesRegex(ValidationError, "cannot exceed 2000"):
            advance_wizard(instance, answer=oversized)
        self.assertFalse(instance.progress.exists())

        progress = WizardStepProgress(
            instance=instance,
            step=self.input_step,
            answer_value=oversized,
        )
        with self.assertRaises(ValidationError):
            progress.full_clean()

    def test_catastrophic_regex_times_out(self):
        self.input_step.text_input_regex = r"(a|aa)+$"
        self.input_step.save()
        instance = start_wizard(self.definition)

        with self.assertRaisesRegex(ValidationError, "validation timed out"):
            advance_wizard(instance, answer=("a" * (MAX_ANSWER_LENGTH - 1)) + "!")
        self.assertFalse(instance.progress.exists())


class DataSourceStoredAnswerTest(TestCase):
    def test_imports_text_fields_and_preserves_explicit_empty_choice_value(self):
        data = parse_definition_data({
            "name": "Imported",
            "steps": [
                {
                    "key": "name",
                    "order": 10,
                    "title": "Name",
                    "is_text_input": True,
                    "answer_key": "service_name",
                    "text_input_prompt": "Service name",
                    "text_input_placeholder": "payments-api",
                    "text_input_help": "Lowercase letters and hyphens.",
                    "text_input_required": True,
                    "text_input_regex": "[a-z-]+",
                    "text_input_validation_message": "Use lowercase letters and hyphens.",
                },
                {
                    "key": "environment",
                    "order": 20,
                    "title": "Environment",
                    "is_multi_choice": True,
                    "answer_key": "environment_suffix",
                    "multi_choice_question": "Environment?",
                    "choices": [
                        {"key": "production", "label": "Production", "value": ""},
                        {"key": "test", "label": "Test"},
                    ],
                },
            ],
        })
        definition = WizardDefinition.objects.create(name="Imported", slug="imported")
        apply_synced_definition(definition, data)

        text_step = definition.steps.get(key="name")
        self.assertTrue(text_step.is_text_input)
        self.assertEqual(text_step.answer_key, "service_name")
        choices = definition.steps.get(key="environment").choices.order_by("order")
        self.assertEqual(choices[0].answer_value, "")
        self.assertIsNone(choices[1].answer_value)

    def test_sync_resets_omitted_fields_before_switching_modes(self):
        definition = WizardDefinition.objects.create(name="Modes", slug="modes")
        apply_synced_definition(definition, {
            "steps": [{
                "key": "mode",
                "title": "Mode",
                "order": 99,
                "instructions": "Old",
                "link_url": "/old/",
                "link_text": "Old link",
                "is_text_input": True,
                "answer_key": "old_answer",
                "text_input_prompt": "Old prompt",
                "text_input_placeholder": "Old placeholder",
                "text_input_help": "Old help",
                "text_input_required": False,
                "text_input_regex": "old",
                "text_input_validation_message": "Old validation",
            }],
        })

        apply_synced_definition(definition, {
            "steps": [{
                "key": "mode",
                "title": "Mode",
                "is_decision": True,
                "decision_question": "Continue?",
            }],
        })

        step = definition.steps.get(key="mode")
        self.assertTrue(step.is_decision)
        self.assertFalse(step.is_text_input)
        self.assertEqual(step.order, 0)
        self.assertEqual(step.instructions, "")
        self.assertEqual(step.link_url, "")
        self.assertEqual(step.link_text, "Open")
        self.assertEqual(step.answer_key, "")
        self.assertEqual(step.text_input_prompt, "")
        self.assertEqual(step.text_input_placeholder, "")
        self.assertEqual(step.text_input_help, "")
        self.assertTrue(step.text_input_required)
        self.assertEqual(step.text_input_regex, "")
        self.assertEqual(step.text_input_validation_message, "")

    def test_sync_can_swap_answer_keys(self):
        definition = WizardDefinition.objects.create(name="Swap", slug="swap")
        first = WizardStep.objects.create(
            definition=definition,
            key="first",
            title="First",
            answer_key="alpha",
        )
        second = WizardStep.objects.create(
            definition=definition,
            key="second",
            title="Second",
            answer_key="beta",
        )

        apply_synced_definition(definition, {
            "steps": [
                {"key": "first", "title": "First", "answer_key": "beta"},
                {"key": "second", "title": "Second", "answer_key": "alpha"},
            ],
        })

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.answer_key, "beta")
        self.assertEqual(second.answer_key, "alpha")

    def test_failed_sync_rolls_back_preliminary_answer_key_clears(self):
        definition = WizardDefinition.objects.create(name="Rollback", slug="rollback")
        first = WizardStep.objects.create(
            definition=definition,
            key="first",
            title="First",
            answer_key="alpha",
        )
        second = WizardStep.objects.create(
            definition=definition,
            key="second",
            title="Second",
            answer_key="beta",
        )

        with self.assertRaises(ValidationError):
            apply_synced_definition(definition, {
                "steps": [
                    {"key": "first", "title": "First", "answer_key": "beta"},
                    {"key": "second", "title": "x" * 201, "answer_key": "alpha"},
                ],
            })

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.answer_key, "alpha")
        self.assertEqual(second.answer_key, "beta")


class WizardStepChoiceFormTest(TestCase):
    def setUp(self):
        definition = WizardDefinition.objects.create(name="Choices", slug="choices")
        step = WizardStep.objects.create(definition=definition, key="choice", title="Choice")
        self.choice = WizardStepChoice.objects.create(
            step=step,
            key="production",
            label="Production",
        )

    def test_existing_fallback_is_represented_by_checked_use_key(self):
        form = WizardStepChoiceForm(instance=self.choice)

        self.assertTrue(form["use_key_as_answer"].value())

    def test_unchecked_use_key_preserves_intentional_empty_value(self):
        form = WizardStepChoiceForm(
            data={
                "key": "production",
                "label": "Production",
                "answer_value": "",
                "order": 0,
                "next_step": "",
            },
            instance=self.choice,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().answer_value, "")

    def test_checked_use_key_stores_null_fallback_even_with_entered_value(self):
        self.choice.answer_value = ""
        self.choice.save()
        form = WizardStepChoiceForm(
            data={
                "key": "production",
                "label": "Production",
                "use_key_as_answer": "on",
                "answer_value": "ignored",
                "order": 0,
                "next_step": "",
            },
            instance=self.choice,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.save().answer_value)


class AdvanceEndpointTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="wizard-admin",
            email="wizard@example.com",
            password="secret",
        )
        self.definition = WizardDefinition.objects.create(name="Input", slug="input")
        self.step = WizardStep.objects.create(
            definition=self.definition,
            key="name",
            title="Name",
            is_text_input=True,
            answer_key="service_name",
            text_input_prompt="Service name",
            text_input_regex="[a-z]+",
            text_input_validation_message="Lowercase only.",
        )

    def test_ui_advance_accepts_and_persists_text_answer(self):
        instance = start_wizard(self.definition, user=self.user)
        request = RequestFactory().post("/", {"answer": "payments", "next": "/"})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = WizardInstanceAdvanceView.as_view()(request, pk=instance.pk)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(instance.progress.get(step=self.step).answer_value, "payments")

    def test_ui_advance_rejects_invalid_text_answer(self):
        instance = start_wizard(self.definition, user=self.user)
        request = RequestFactory().post("/", {"answer": "INVALID", "next": "/"})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = WizardInstanceAdvanceView.as_view()(request, pk=instance.pk)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(instance.progress.exists())
        self.assertIn("Lowercase only.", " ".join(str(message) for message in request._messages))

    def test_ui_advance_rejects_excessive_text_answer(self):
        instance = start_wizard(self.definition, user=self.user)
        request = RequestFactory().post(
            "/",
            {"answer": "a" * (MAX_ANSWER_LENGTH + 1), "next": "/"},
        )
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = WizardInstanceAdvanceView.as_view()(request, pk=instance.pk)

        self.assertEqual(response.status_code, 302)
        self.assertFalse(instance.progress.exists())
        self.assertIn("cannot exceed 2000", " ".join(str(message) for message in request._messages))

    def test_api_advance_rejects_invalid_answer_and_serializes_answers(self):
        instance = start_wizard(self.definition, user=self.user)
        view = WizardInstanceViewSet.as_view({"post": "advance"})
        request = APIRequestFactory().post("/", {"answer": "INVALID"}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=instance.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Lowercase only.", str(response.data))
        self.assertFalse(instance.progress.exists())

        request = APIRequestFactory().post("/", {"answer": "payments"}, format="json")
        force_authenticate(request, user=self.user)
        response = view(request, pk=instance.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["answers"], {"service_name": "payments"})
        self.assertEqual(WizardInstanceSerializer(instance).data["answers"], {"service_name": "payments"})

    def test_api_advance_rejects_excessive_text_answer(self):
        instance = start_wizard(self.definition, user=self.user)
        view = WizardInstanceViewSet.as_view({"post": "advance"})
        request = APIRequestFactory().post(
            "/",
            {"answer": "a" * (MAX_ANSWER_LENGTH + 1)},
            format="json",
        )
        force_authenticate(request, user=self.user)

        response = view(request, pk=instance.pk)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(instance.progress.exists())
