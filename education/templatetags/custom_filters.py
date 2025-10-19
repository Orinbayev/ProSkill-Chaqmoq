from django import template

register = template.Library()

@register.filter
def sumpositive(items, field):
    """Massivdagi faqat musbat qiymatlarni yig‘adi."""
    return sum(getattr(i, field, 0) for i in items if getattr(i, field, 0) > 0)

@register.filter
def sumnegative(items, field):
    """Massivdagi faqat manfiy qiymatlarni yig‘adi."""
    return sum(getattr(i, field, 0) for i in items if getattr(i, field, 0) < 0)

@register.filter
def dict_get(d, key):
    """Lug‘atdan (dict) kalit bo‘yicha qiymatni qaytaradi."""
    if not d or not isinstance(d, dict):
        return None
    return d.get(key)
