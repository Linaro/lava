import logging
import os
import sys

from json_schema_validator.errors import ValidationError
from lava.tool.command import Command

from lava_dispatcher.config import get_config, get_device_config
from lava_dispatcher.job import LavaTestJob, validate_job_data


class dispatch(Command):
    """
    Run test scenarios on virtual and physical hardware
    """

    @classmethod
    def register_arguments(self, parser):
        # When we're working inside a virtual environment use venv-relative
        # configuration directory. This works well with lava-deployment-tool
        # and the directory layout it currently provides but will need to be
        # changed for codeline support.
        if "VIRTUAL_ENV" in os.environ:
            default_config_dir = os.path.join(
                os.environ["VIRTUAL_ENV"], "etc", "lava-dispatcher")
        else:
            default_config_dir = None

        parser.add_argument(
            "--oob-fd",
            default=None,
            type=int,
            help="Used internally by LAVA scheduler.")
        parser.add_argument(
            "--config-dir",
            default=default_config_dir,
            help="Configuration directory override (currently %(default)s")
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

    def invoke(self):
        if self.args.oob_fd:
            oob_file = os.fdopen(self.args.oob_fd, 'w')
        else:
            oob_file = sys.stderr

        # config the python logging
        # FIXME: move to lava-tool
        FORMAT = '<LAVA_DISPATCHER>%(asctime)s %(levelname)s: %(message)s'
        DATEFMT= '%Y-%m-%d %I:%M:%S %p'
        logging.basicConfig(format=FORMAT,datefmt=DATEFMT)
        config = get_config("lava-dispatcher", self.args.config_dir)
        logging_level = config.get("LOGGING_LEVEL")
        logging.root.setLevel(int(logging_level))

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
        job = LavaTestJob(jobdata, oob_file, config)

        #FIXME Return status
        if self.args.validate:
            try:
                validate_job_data(job.job_data)
            except ValidationError as e:
                print e
        else:
            job.run()


class connect(Command):
    """
    """
    @classmethod
    def register_arguments(self, parser):
        # When we're working inside a virtual environment use venv-relative
        # configuration directory. This works well with lava-deployment-tool
        # and the directory layout it currently provides but will need to be
        # changed for codeline support.
        if "VIRTUAL_ENV" in os.environ:
            default_config_dir = os.path.join(
                os.environ["VIRTUAL_ENV"], "etc", "lava-dispatcher")
        else:
            default_config_dir = None

        parser.add_argument(
            "--config-dir",
            default=default_config_dir,
            help="Configuration directory override (currently %(default)s")
        parser.add_argument(
            "device",
            help="Device to connect to.")

    def invoke(self):
        c = get_device_config(self.args.device, self.args.config_dir)
        os.execlp('sh', 'sh', '-c', c.get('connection_command'))
