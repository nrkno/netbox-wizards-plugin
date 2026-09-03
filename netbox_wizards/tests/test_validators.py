from unittest import TestCase

from django.core.exceptions import ValidationError

from netbox_wizards.validators import validate_safe_link_url, validate_safe_markdown


class SafeLinkUrlValidatorTest(TestCase):
    def test_accepts_http_urls_and_root_relative_paths(self):
        for value in (
            "https://netbox.example.com/dcim/devices/1/",
            "http://docs.example.com/guide",
            "/extras/scripts/run/",
        ):
            with self.subTest(value=value):
                validate_safe_link_url(value)

    def test_rejects_executable_and_protocol_relative_urls(self):
        for value in (
            "javascript:alert(1)",
            "JaVaScRiPt:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
            "//attacker.example/phishing",
            "/\\attacker.example/phishing",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_safe_link_url(value)


class SafeMarkdownValidatorTest(TestCase):
    def test_accepts_normal_markdown(self):
        validate_safe_markdown(
            "Use **care** and see [the device](https://netbox.example.com/dcim/devices/1/)."
        )
        validate_safe_markdown("Run the [local script](/extras/scripts/run/).")
        validate_safe_markdown("See [details](details/) or [this section](#details).")
        validate_safe_markdown("Contact <operator@example.com>.")

    def test_rejects_raw_html(self):
        for value in (
            "<script>alert(1)</script>",
            '<img src="x" onerror="alert(1)">',
            "<svg/onload=alert(1)>",
            "<!-- hidden manipulation -->",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_safe_markdown(value)

    def test_rejects_unsafe_markdown_destinations(self):
        for value in (
            "[click](javascript:alert(1))",
            "[click](java&#x73;cript:alert(1))",
            "[click][target]\n\n[target]: data:text/html,payload",
            "<vbscript:msgbox(1)>",
            "[click](//attacker.example/phishing)",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    validate_safe_markdown(value)
