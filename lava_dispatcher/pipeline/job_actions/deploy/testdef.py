from lava_dispatcher.pipeline import Action


class TestDefinitionAction(Action):

    def __init__(self):
        super(TestDefinitionAction, self).__init__()
        self.name = "test-definition"
        self.description = "load test definitions into image"
        self.summary = "loading test definitions"
