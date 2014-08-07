from linaro_django_xmlrpc.models import ExposedAPI
from linaro_django_xmlrpc.globals import mapper


class ExampleAPI(ExposedAPI):

    def foo(self):
        """
        Return "bar"
        """
        return "bar"

    def whoami(self):
        if self.user:
            return self.user.username
        else:
            return None
