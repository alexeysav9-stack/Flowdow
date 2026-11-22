"""Template tags for data sources presentation."""

from typing import Any

from django import template

register = template.Library()


@register.filter(name="get_item")
def get_item(dictionary: Any, key: Any) -> Any:
    """Retrieves item from dictionary dynamically by key."""
    if isinstance(dictionary, dict):
        return dictionary.get(key, "")
    return ""

