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

@register.filter
def to_uz(value):
    """Translates Russian time units to Uzbek for timesince filter"""
    if not value: return value
    replacements = {
        'день': 'kun', 'дня': 'kun', 'дней': 'kun',
        'час': 'soat', 'часа': 'soat', 'часов': 'soat',
        'минута': 'daqiqa', 'минуты': 'daqiqa', 'минут': 'daqiqa',
        'неделя': 'hafta', 'недели': 'hafta', 'недель': 'hafta',
        'месяц': 'oy', 'месяца': 'oy', 'месяцев': 'oy',
        'год': 'yil', 'года': 'yil', 'лет': 'yil',
    }
    import re
    res = str(value)
    for ru, uz in replacements.items():
        res = re.sub(rf'\b{ru}\b', uz, res)
    return res
    