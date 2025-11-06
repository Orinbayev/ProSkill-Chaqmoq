from django import template
register = template.Library()

@register.filter
def get_month_name(value):
    oylar = [
        '', 'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
        'Iyul', 'Avgust', 'Sentyabr', 'Oktyabr', 'Noyabr', 'Dekabr'
    ]
    try:
        return oylar[int(value)]
    except (ValueError, IndexError):
        return value

@register.filter
def to(value, end):
    """For loop range generator"""
    return range(value, end + 1)

@register.filter
def get_years_until(value, end):
    return range(value, end + 1)
    