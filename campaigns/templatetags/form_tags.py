from django import template

register = template.Library()

@register.filter(name='addclass')
def addclass(field, css):
    if hasattr(field, 'field'):
        return field.as_widget(attrs={'class': css})
    return field 