from django import template

register = template.Library()

@register.filter(name="absval")
def absval(value):
    """
    Qiymatning absolut qiymatini qaytaradi.
    Raqam bo'lmasa 0 qaytaradi.
    """
    try:
        # avval int, bo'lmasa float sifatida urinamiz
        return abs(int(value))
    except (TypeError, ValueError):
        try:
            return abs(float(value))
        except (TypeError, ValueError):
            return 0
