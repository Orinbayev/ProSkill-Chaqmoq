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


@register.filter
def has_feature(center, code):
    """Template'da tarif featurini tekshirish:
    {% if request.center|has_feature:"ai_assistant" %} ... {% endif %}
    CORE featurelar doim True; superuser bypass view/context darajasida.
    """
    if center is None or not code:
        return False
    try:
        return bool(center.has_feature(code))
    except Exception:
        return False
