# accounts/templatetags/form_tags.py
from django import template
register = template.Library()

@register.filter(name="add_class")
def add_class(field, css):
    try:
        attrs = field.field.widget.attrs.copy()
        attrs["class"] = (attrs.get("class", "") + " " + css).strip()
        return field.as_widget(attrs=attrs)
    except Exception:
        return field
    
@register.filter
def get_item(d, key):
    try:
        return d.get(key)
    except Exception:
        return None

