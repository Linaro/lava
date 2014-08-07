from django import template
from django.db.models import fields
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


class LineNumbers(template.Node):
    def __init__(self, text, prefix, style):
        self.text = template.Variable(text)
        self.prefix = template.Variable(prefix)
        self.style = template.Variable(style)

    def render(self, context):
        text = self.text.resolve(context)
        prefix = self.prefix.resolve(context)
        style = self.style.resolve(context)

        ret = "<div>\n"
        for index, line in enumerate(text.splitlines()):
            name = "L_%s_%s" % (prefix, index)
            display = "%s.%s" % (prefix, index)

            ret += "<code id=\"L_%s_%s\" class=\"line %s\"><a href=\"#%s\">%s</a> &nbsp;%s</code>\n" % \
                (prefix, index, style, name, display,
                 mark_safe(escape(line).encode('ascii', 'xmlcharrefreplace')))

        ret += "</div>"

        return ret


@register.tag('linenumbers')
def do_linenumbers(parser, token):
    try:
        tag_name, text, prefix, style = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires 3 arguments" %
                                           token.contents.split()[0])
    return LineNumbers(text, prefix, style)
