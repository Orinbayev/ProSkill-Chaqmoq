from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """
    Template ichida dict'dan qiymat olish:
    {{ pricing|get_item:p.code }}
    """
    if d is None:
        return None
    try:
        return d.get(key)
    except Exception:
        try:
            return d[key]
        except Exception:
            return None
