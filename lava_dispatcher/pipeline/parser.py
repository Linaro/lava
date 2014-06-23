import copy
import yaml

from yaml.composer import Composer
from yaml.constructor import Constructor
from lava_dispatcher.pipeline import *


class JobParser(object):

    loader = None

    # annotate every object in data with line numbers so we can use
    # them is user-friendly validation messages, combined with the action.level
    # each action will also include an output_line to map to the stdout log,
    # once executed.

    def compose_node(self, parent, index):
        # the line number where the previous token has ended (plus empty lines)
        line = self.loader.line
        node = Composer.compose_node(self.loader, parent, index)
        node.__line__ = line + 1
        return node

    def construct_mapping(self, node, deep=False):
        mapping = Constructor.construct_mapping(self.loader, node, deep=deep)
        mapping['yaml_line'] = node.__line__
        return mapping

    def parse(self, io):
        self.loader = yaml.Loader(io)
        self.loader.compose_node = self.compose_node
        self.loader.construct_mapping = self.construct_mapping
        data = self.loader.get_single_data()

        pipeline = Pipeline()
        for action_data in data['actions']:
            line = action_data.pop('yaml_line', None)
            for name in action_data:
                action_class = Action.find(name)
                action = action_class(line=line)
                # put parameters (like rootfs_type, results_dir) into the actions.
                if type(action_data[name]) == dict:
                    action.parameters = action_data[name]
                elif name == "commands":
                    # FIXME
                    pass
                elif type(action_data[name]) == list:
                    for param in action_data[name]:
                        action.parameters = param
                action.summary = name
                pipeline.add_action(action)
                # uncomment for debug
                # print action.parameters

        # the only parameters sent to the job are job parameters
        # like job_name, logging_level or target_group.
        data.pop('actions')
        job = Job(pipeline, data)
        return job
