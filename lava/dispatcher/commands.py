import argparse
import json
import logging
import os
import sys

from json_schema_validator.errors import ValidationError
from lava.tool.command import Command
from lava.tool.errors import CommandError
from lava.dispatcher.node import NodeDispatcher
import lava_dispatcher.config
from lava_dispatcher.config import get_config, get_device_config, get_devices
from lava_dispatcher.job import LavaTestJob, validate_job_data


class SetUserConfigDirAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        lava_dispatcher.config.custom_config_path = value


class SetCustomConfigFile(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        lava_dispatcher.config.custom_config_file = value


class DispatcherCommand(Command):
    @classmethod
    def register_arguments(cls, parser):
        super(DispatcherCommand, cls).register_arguments(parser)
        parser.add_argument(
            "--config-dir",
            default=None,
            action=SetUserConfigDirAction,
            help="Configuration directory override (currently %(default)s")
        parser.add_argument(
            "--config",
            default=None,
            action=SetCustomConfigFile,
            help="Custom config file")


class devices(DispatcherCommand):
    """
    Lists all the configured devices in this LAVA instance.
    """
    def invoke(self):
        for d in get_devices():
            print d.hostname


class dispatch(DispatcherCommand):
    """
    Run test scenarios on virtual and physical hardware
    """

    @classmethod
    def register_arguments(cls, parser):
        super(dispatch, cls).register_arguments(parser)
        parser.add_argument(
            "--oob-fd",
            default=None,
            type=int,
            help="Used internally by LAVA scheduler.")
        parser.add_argument(
            "--output-dir",
            default=None,
            help="Directory to put structured output in.")
        parser.add_argument(
            "--validate", action='store_true',
            help="Just validate the job file, do not execute any steps.")
        parser.add_argument(
            "--job-id", action='store', default=None,
            help=("Set the scheduler job identifier. "
                  "This alters process name for easier debugging"))
        parser.add_argument(
            "job_file",
            metavar="JOB",
            help="Test scenario file")
        parser.add_argument(
            "--target",
            default=None,
            help="Run the job on a specific target device"
        )

    def invoke(self):

        if os.getuid() != 0:
            logging.error("lava dispatch has to be run as root")
            exit(1)

        if self.args.oob_fd:
            oob_file = os.fdopen(self.args.oob_fd, 'w')
        else:
            oob_file = sys.stderr

        # config the python logging
        # FIXME: move to lava-tool
        # XXX: this is horrible, but: undo the logging setup lava-tool has
        # done.
        del logging.root.handlers[:]
        del logging.root.filters[:]
        FORMAT = '<LAVA_DISPATCHER>%(asctime)s %(levelname)s: %(message)s'
        DATEFMT = '%Y-%m-%d %I:%M:%S %p'
        logging.basicConfig(format=FORMAT, datefmt=DATEFMT)
        config = get_config()
        logging.root.setLevel(config.logging_level)

        # Set process id if job-id was passed to dispatcher
        if self.args.job_id:
            try:
                from setproctitle import getproctitle, setproctitle
            except ImportError:
                logging.warning(
                    ("Unable to set import 'setproctitle', "
                     "process name cannot be changed"))
            else:
                setproctitle("%s [job: %s]" % (
                    getproctitle(), self.args.job_id))

        # Load the scenario file
        with open(self.args.job_file) as stream:
            jobdata = stream.read()
            json_jobdata = json.loads(jobdata)

        # detect multinode and start a NodeDispatcher to work with the LAVA Coordinator.
        if not self.args.validate:
            if 'target_group' in json_jobdata:
                node = NodeDispatcher(json_jobdata, oob_file, self.args.output_dir)
                node.run()
                # the NodeDispatcher has started and closed.
                exit(0)
        if self.args.target is None:
            if 'target' not in json_jobdata:
                logging.error("The job file does not specify a target device. "
                              "You must specify one using the --target option.")
                exit(1)
        else:
            json_jobdata['target'] = self.args.target
            jobdata = json.dumps(json_jobdata)
        if self.args.output_dir and not os.path.isdir(self.args.output_dir):
            os.makedirs(self.args.output_dir)
        job = LavaTestJob(jobdata, oob_file, config, self.args.output_dir)

        #FIXME Return status
        if self.args.validate:
            try:
                validate_job_data(job.job_data)
            except ValidationError as e:
                print e
        else:
            job.run()


class DeviceCommand(DispatcherCommand):

    @classmethod
    def register_arguments(cls, parser):
        super(DeviceCommand, cls).register_arguments(parser)
        parser.add_argument('device')

    @property
    def device_config(self):
        try:
            return get_device_config(self.args.device)
        except Exception:
            raise CommandError("no such device: %s" % self.args.device)


class connect(DeviceCommand):

    def invoke(self):
        os.execlp(
            'sh', 'sh', '-c', self.device_config.connection_command)


class power_cycle(DeviceCommand):

    def invoke(self):
        command = self.device_config.hard_reset_command
        if not command:
            raise CommandError(
                "%s does not have a power cycle command configured" %
                self.args.device)
        os.system(command)
