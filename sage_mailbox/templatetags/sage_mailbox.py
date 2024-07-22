from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def get_last_path_part(context):
    request = context['request']
    path_parts = request.path.strip('/').split('/')
    return path_parts[-1] if path_parts else ''
