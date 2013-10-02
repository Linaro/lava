from django import template
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter


register = template.Library()


class StylizeNode(template.Node):

    def __init__(self, nodelist, *varlist):
        self.nodelist, self.vlist = (nodelist, varlist)

    def render(self, context):
        style = 'text'
        if len(self.vlist) > 0:
            style = template.resolve_variable(self.vlist[0], context)
        code = self.nodelist.render(context)
        lexer = get_lexer_by_name(style, encoding='UTF-8')
        formatter = HtmlFormatter(cssclass="pygments")
        return highlight(code, lexer, formatter) 


@register.tag
def stylize(parser, token):
    """
    Usage: {% stylize "language" %}...language text...{% endstylize %}
    """
    nodelist = parser.parse(('endstylize',))
    parser.delete_first_token()
    return StylizeNode(nodelist, *token.contents.split()[1:])
