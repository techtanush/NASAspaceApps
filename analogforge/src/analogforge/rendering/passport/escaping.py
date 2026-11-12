"""Output encoding helpers. JSON intentionally preserves the original strings."""

from markupsafe import Markup, escape


def html_text(value: object) -> Markup:
    return escape("Unknown" if value is None else str(value))


def spreadsheet_cell(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text
