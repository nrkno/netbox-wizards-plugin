import html
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_DANGEROUS_HTML_TAG = re.compile(
    r"<\s*/?\s*(?:script|iframe|object|embed|svg|math|style|link|meta|base|form|input|button|textarea|select)"
    r"(?:\s|/?>)",
    re.IGNORECASE,
)
_DANGEROUS_HTML_ATTRIBUTE = re.compile(
    r"\s(?:on[a-z]+|style|srcdoc)\s*=",
    re.IGNORECASE,
)
_HTML_URI_ATTRIBUTE = re.compile(
    r"\s(?:href|src|action|formaction|poster|background)\s*=\s*(?:([\"'])(.*?)\1|([^\s>]+))",
    re.IGNORECASE | re.DOTALL,
)
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
    """Reject active HTML and executable link targets while preserving formatting."""
    if not value:
        return
    if not isinstance(value, str):
        raise ValidationError("Markdown content must be text.", code="invalid_markdown")
    normalized = html.unescape(value)
    if _DANGEROUS_HTML_TAG.search(normalized) or _DANGEROUS_HTML_ATTRIBUTE.search(normalized):
        raise ValidationError(
            "Active HTML elements and attributes are not allowed.",
            code="unsafe_html",
        )
    for match in _HTML_URI_ATTRIBUTE.finditer(normalized):
        _validate_markdown_link_url(match.group(2) or match.group(3))

    link_destinations = (
        _MARKDOWN_INLINE_DESTINATION.findall(normalized)
        + _MARKDOWN_REFERENCE_DESTINATION.findall(normalized)
        + _MARKDOWN_AUTOLINK.findall(normalized)
    )
    for destination in link_destinations:
        _validate_markdown_link_url(destination)
