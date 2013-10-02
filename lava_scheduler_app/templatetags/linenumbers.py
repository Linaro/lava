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
        ret = "<table><tr><td>"
        for i in range(0, len(text.splitlines())):
            name = "L_%s_%s" % (prefix, i)
            if (i == 0):
                display = "Section %s" % (prefix)
            else:
                display = "%s.%s" % (prefix, i)
            ret += "<div class=\"line\"><a name=\"%s\"></a> \
                <a href=\"#%s\">%s</a></div>" % (name, name, display)

        ret += "</td><td class=\"code\"><div class=\"containter\"> \
            <pre class=\"log_%s\">" % (style)

        for index, line in enumerate(text.splitlines()):
            ret += "<div id=\"L_%s_%s\" class=\"line\"> &nbsp;%s</div>" % \
                (prefix,
                 index,
                 mark_safe(escape(line).encode('ascii', 'xmlcharrefreplace')))

        ret += "</pre></div></td><tr></table>"

        return ret

@register.tag('linenumbers')
def do_linenumbers(parser, token):
    try:
        tag_name, text, prefix, style = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError("%r tag requires 3 arguments" % \
            token.contents.split()[0])
    return LineNumbers(text, prefix, style)
