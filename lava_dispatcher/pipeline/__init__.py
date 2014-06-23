import sys
from collections import OrderedDict
from lava_dispatcher.pipeline.action import *
from lava_dispatcher.pipeline.serial import *
from lava_dispatcher.pipeline.ssh import *
from lava_dispatcher.pipeline.shell import *
from lava_dispatcher.pipeline.run import *

from lava_dispatcher.pipeline.job_actions.boot import *
from lava_dispatcher.pipeline.job_actions.commands import *
from lava_dispatcher.pipeline.job_actions.deploy import *
from lava_dispatcher.pipeline.job_actions.logic import *
from lava_dispatcher.pipeline.job_actions.submit import *
from lava_dispatcher.pipeline.job_actions.test import *


class Pipeline(object):

    def __init__(self, parent=None):
        self.children = {}
        self.actions = []
        self.summary = "pipeline"
        self.parent = None
        self.branch_level = 1  # the level of the last added child
        if not parent:
            self.children = {self: self.actions}
        elif not parent.level:
            raise RuntimeError("Tried to create a pipeline with an invalid parent.")
        else:
            # parent must be an Action
            if type(parent) != Action:
                raise RuntimeError("Internal pipelines need an Action as a parent")
            self.parent = parent
            self.branch_level = parent.level

    def add_action(self, action):

        if not action or not issubclass(type(action), Action):
            raise RuntimeError("Only actions can be added to a pipeline: %s" % action)
        if not action:
            raise RuntimeError("Unable to add empty action to pipeline")
        self.actions.append(action)
        action.level = "%s.%s" % (self.branch_level, len(self.actions))
        if self.parent:
            self.children.update({self: self.actions})
            self.parent.pipeline = self
        else:
            action.level = "%s" % (len(self.actions))

    def _describe(self, structure):
        for action in self.actions:
            structure[action.level] = {
                'description': action.description,
                'summary': action.summary,
                'content': action.explode()
            }
            if not action.pipeline:
                continue
            action.pipeline._describe(structure)

    def describe(self):
        """
        Describe the current pipeline, recursing through any
        internal pipelines.
        :return: JSON string of the structure
        """
        structure = OrderedDict()
        self._describe(structure)
        return structure

    @property
    def errors(self):
        sub_action_errors = [a.errors for a in self.actions]
        return reduce(lambda a, b: a + b, sub_action_errors)

    def run_actions(self, connection, args=None):
        for action in self.actions:
            new_connection = action.run(connection, args)
            if new_connection:
                connection = new_connection
        return connection

    def prepare_actions(self):
        for action in self.actions:
            action.prepare()

    def post_process_actions(self):
        for action in self.actions:
            action.post_process()
