from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Безопасное получение значения из словаря"""
    try:
        return dictionary.get(key)
    except (AttributeError, KeyError):
        return None

@register.filter
def div(value, arg):
    """Делит значение на аргумент"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return None
    
@register.filter
def pluralize_ru(value, arg="вопрос,вопроса,вопросов"):
    forms = arg.split(',')
    try:
        number = abs(int(value))
    except (ValueError, TypeError):
        return ''

    if number % 10 == 1 and number % 100 != 11:
        form = forms[0]
    elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        form = forms[1]
    else:
        form = forms[2]

    return form