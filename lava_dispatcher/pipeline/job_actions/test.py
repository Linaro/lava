from lava_dispatcher.pipeline import Action


class TestAction(Action):

    name = 'test'

    def __init__(self):
        super(TestAction, self).__init__()

    def validate(self):
        if 'definitions' in self.parameters:
            for testdef in self.parameters['definitions']:
                if 'repository' not in testdef:
                    self.errors = "Repository missing from test definition"

    def run(self, connection, args=None):
        self._log("Loading test definitions")
        return connection
