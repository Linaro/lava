from django import template


register = template.Library()


class CallNode(template.Node):
    def __init__(self, func, args, name, nodelist):
        self.func = func
        self.args = args
        self.name = name
        self.nodelist = nodelist

    def __repr__(self):
        return "<CallNode>"

    def _lookup_func(self, context):
        parts = self.func.split('.')
        current = context[parts[0]] 
        for part in parts[1:]:
            if part.startswith("_"):
                raise ValueError(
                    "Function cannot traverse private implementation attributes")
            current = getattr(current, part)
        return current

    def render(self, context):
        try:
            func = self._lookup_func(context) 
            values = [template.Variable(arg).resolve(context) for arg in self.args]
            context.push()
            context[self.name] = func(*values)
            output = self.nodelist.render(context)
            context.pop()
            return output
        except Exception as ex:
            import logging
            logging.exception("Unable to call %s with %r: %s",
                              self.func, self.args, ex)
            raise

def do_call(parser, token):
    """
    Adds a value to the context (inside of this block) for caching and easy
    access.

    For example::

        {% call func 1 2 3 as result %}
            {{ result }}
        {% endcall %}
    """
    bits = list(token.split_contents())
    if len(bits) < 2 or bits[-2] != "as":
        raise template.TemplateSyntaxError(
            "%r expected format is 'call func [args] [as name]'" % bits[0])
    func = bits[1]
    args = bits[2:-2]
    name = bits[-1]
    nodelist = parser.parse(('endcall',))
    parser.delete_first_token()
    return CallNode(func, args, name, nodelist)

do_call = register.tag('call', do_call)
