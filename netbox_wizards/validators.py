import html
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_HTML_TAG = re.compile(r"<\s*(?:!--|/?\s*[a-zA-Z][a-zA-Z0-9-]*(?:>|[\s/][^<>]*>))")
_MARKDOWN_INLINE_DESTINATION = re.compile(r"!?\[[^\]]*\]\(\s*(?:<\s*)?([^)>\s]+)", re.MULTILINE)
_MARKDOWN_REFERENCE_DESTINATION = re.compile(r"^\s*\[[^\]]+\]:\s*(?:<\s*)?([^>\s]+)", re.MULTILINE)
_MARKDOWN_AUTOLINK = re.compile(r"<\s*([^<>\s]+)\s*>")
_ALLOWED_LINK_SCHEMES = {"http", "https"}
_ALLOWED_MARKDOWN_LINK_SCHEMES = _ALLOWED_LINK_SCHEMES | {"mailto"}
_UNSAFE_LINK_MESSAGE = "Enter an HTTP(S) URL or a root-relative path beginning with '/'."


def validate_safe_link_url(value):
    """Allow web URLs and local NetBox paths, but never executable URI schemes."""
    if not value:
        return
    if not isinstance(value, str) or _CONTROL_CHARACTERS.search(value):
        raise ValidationError(_UNSAFE_LINK_MESSAGE, code="unsafe_url")

    normalized = html.unescape(value).strip()
    parsed = urlsplit(normalized)

    if parsed.scheme:
        if parsed.scheme.lower() not in _ALLOWED_LINK_SCHEMES or not parsed.netloc:
            raise ValidationError(_UNSAFE_LINK_MESSAGE, code="unsafe_url")
        return

    if not normalized.startswith("/") or normalized.startswith(("//", "/\\")):
        raise ValidationError(_UNSAFE_LINK_MESSAGE, code="unsafe_url")


def _validate_markdown_link_url(value):
    if _CONTROL_CHARACTERS.search(value):
        raise ValidationError("Markdown contains an unsafe link.", code="unsafe_url")

    normalized = html.unescape(value).strip()
    parsed = urlsplit(normalized)
    if parsed.scheme and parsed.scheme.lower() not in _ALLOWED_MARKDOWN_LINK_SCHEMES:
        raise ValidationError("Markdown contains an unsafe link.", code="unsafe_url")
    if not parsed.scheme and normalized.startswith(("//", "\\\\")):
        raise ValidationError("Markdown contains an unsafe link.", code="unsafe_url")


def validate_safe_markdown(value):
    """Reject raw HTML and executable link targets while preserving normal Markdown."""
    if not value:
        return
    if not isinstance(value, str):
        raise ValidationError("Markdown content must be text.", code="invalid_markdown")
    if _HTML_TAG.search(value):
        raise ValidationError(
            "Raw HTML is not allowed. Use Markdown formatting instead.",
            code="unsafe_html",
        )

    link_destinations = (
        _MARKDOWN_INLINE_DESTINATION.findall(value)
        + _MARKDOWN_REFERENCE_DESTINATION.findall(value)
        + _MARKDOWN_AUTOLINK.findall(value)
    )
    for destination in link_destinations:
        _validate_markdown_link_url(destination)
