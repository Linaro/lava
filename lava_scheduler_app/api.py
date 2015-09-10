import os
import xmlrpclib
import json
import yaml
import jinja2
from django.core.exceptions import PermissionDenied
from simplejson import JSONDecodeError
from django.db.models import Count
from linaro_django_xmlrpc.models import ExposedAPI
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    JSONDataError,
    DevicesUnavailableException,
    TestJob,
    Worker,
    DeviceDictionary,
    SubmissionException,
)
from lava_scheduler_app.views import (
    SumIf,
    get_restricted_job
)
from lava_scheduler_app.utils import (
    devicedictionary_to_jinja2,
    jinja_template_path,
)
from lava_scheduler_app.schema import validate_submission, validate_device


class SchedulerAPI(ExposedAPI):

    def submit_job(self, job_data):
        """
        Name
        ----
        `submit_job` (`job_data`)

        Description
        -----------
        Submit the given job data which is in LAVA job JSON format as a new
        job to LAVA scheduler.

        Arguments
        ---------
        `job_data`: string
            Job JSON string.

        Return value
        ------------
        This function returns an XML-RPC integer which is the newly created
        job's id,  provided the user is authenticated with an username and
        token.
        """
        self._authenticate()
        if not self.user.has_perm('lava_scheduler_app.add_testjob'):
            raise xmlrpclib.Fault(
                403, "Permission denied.  User %r does not have the "
                "'lava_scheduler_app.add_testjob' permission.  Contact "
                "the administrators." % self.user.username)
        is_json = True
        is_yaml = False
        try:
            json.loads(job_data)
        except (AttributeError, JSONDecodeError, ValueError) as exc:
            is_json = False
            try:
                # only try YAML if this is not JSON
                # YAML can parse JSON as YAML, JSON cannot parse YAML at all
                yaml_data = yaml.load(job_data)
            except yaml.YAMLError as exc:
                # neither yaml nor json loaders were able to process the submission.
                raise xmlrpclib.Fault(400, "Loading job submission failed: %s." % exc)

            # validate against the submission schema.
            is_yaml = validate_submission(yaml_data)  # raises SubmissionException if invalid.

        try:
            if is_json:
                job = TestJob.from_json_and_user(job_data, self.user)
            elif is_yaml:
                job = TestJob.from_yaml_and_user(job_data, self.user)
            else:
                raise xmlrpclib.Fault(400, "Unable to determine whether job is JSON or YAML.")
        except (JSONDataError, JSONDecodeError, ValueError) as exc:
            raise xmlrpclib.Fault(400, "Decoding job submission failed: %s." % exc)
        except Device.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified device not found.")
        except DeviceType.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified device type not found.")
        except DevicesUnavailableException as e:
            raise xmlrpclib.Fault(400, str(e))
        if isinstance(job, type(list())):
            return [j.sub_id for j in job]
        else:
            return job.id

    def resubmit_job(self, job_id):
        """
        Name
        ----
        `resubmit_job` (`job_id`)

        Description
        -----------
        Resubmit the given job reffered by its id.

        Arguments
        ---------
        `job_id`: string
            The job's id which should be re-submitted.

        Return value
        ------------
        This function returns an XML-RPC integer which is the newly created
        job's id,  provided the user is authenticated with an username and
        token.
        """
        self._authenticate()
        if not self.user.has_perm('lava_scheduler_app.add_testjob'):
            raise xmlrpclib.Fault(
                403, "Permission denied.  User %r does not have the "
                "'lava_scheduler_app.add_testjob' permission.  Contact "
                "the administrators." % self.user.username)
        try:
            job = get_restricted_job(self.user, job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")
        if job.is_multinode:
            return self.submit_job(job.multinode_definition)
        elif job.is_vmgroup:
            return self.submit_job(job.vmgroup_definition)
        else:
            return self.submit_job(job.definition)

    def cancel_job(self, job_id):
        """
        Name
        ----
        `cancel_job` (`job_id`)

        Description
        -----------
        Cancel the given job reffered by its id.

        Arguments
        ---------
        `job_id`: string
            Job id which should be canceled.

        Return value
        ------------
        None. The user should be authenticated with an username and token.
        """
        self._authenticate()
        if not job_id:
            raise xmlrpclib.Fault(400, "Bad request: TestJob id was not "
                                  "specified.")
        try:
            job = get_restricted_job(self.user, job_id)
        except PermissionDenied:
            raise xmlrpclib.Fault(
                401, "Permission denied for user to job %s" % job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")

        if not job.can_cancel(self.user):
            raise xmlrpclib.Fault(403, "Permission denied.")
        if job.is_multinode:
            multinode_jobs = TestJob.objects.filter(
                target_group=job.target_group)
            for multinode_job in multinode_jobs:
                multinode_job.cancel(self.user)
        elif job.is_vmgroup:
            for vmgroup_job in job.sub_jobs_list:
                vmgroup_job.cancel(self.user)
        else:
            job.cancel(self.user)
        return True

    def validate_yaml(self, yaml_string):
        """
        Name
        ----
        validate_yaml (yaml_job_data)

        Description
        -----------
        Validate the supplied pipeline YAML against the submission schema.

        Note: this does not validate the job itself, just the YAML against the
        submission schema. A job which validates against the schema can still be
        an invalid job for the dispatcher and such jobs will be accepted as Submitted,
        scheduled and then marked as Incomplete with a failure comment. Full validation
        only happens after a device has been assigned to the Submitted job.

        Arguments
        ---------
        'yaml_job_data': string

        Return value
        ------------
        Raises an Exception if the yaml_job_data is invalid.
        """
        try:
            # YAML can parse JSON as YAML, JSON cannot parse YAML at all
            yaml_data = yaml.load(yaml_string)
        except yaml.YAMLError as exc:
            raise xmlrpclib.Fault(400, "Decoding job submission failed: %s." % exc)
        try:
            # validate against the submission schema.
            validate_submission(yaml_data)  # raises SubmissionException if invalid.
        except SubmissionException as exc:
            raise xmlrpclib.Fault(400, "Invalid YAML submission: %s" % exc)

    def job_output(self, job_id, offset=0):
        """
        Name
        ----
        `job_output` (`job_id`, `offset=0`)

        Description
        -----------
        Get the output of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.
        `offset`: integer
            Offset from which to start reading the output file specified in bytes.
            It defaults to 0.

        Return value
        ------------
        This function returns an XML-RPC binary data of output file, provided
        the user is authenticated with an username and token.
        """
        self._authenticate()
        if not job_id:
            raise xmlrpclib.Fault(400, "Bad request: TestJob id was not "
                                  "specified.")
        try:
            job = get_restricted_job(self.user, job_id)
        except PermissionDenied:
            raise xmlrpclib.Fault(
                401, "Permission denied for user to job %s" % job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")

        output_file = job.output_file()
        if output_file:
            output_file.seek(offset)
            return xmlrpclib.Binary(output_file.read().encode('UTF-8'))
        else:
            raise xmlrpclib.Fault(404, "Job output not found.")

    def all_devices(self):
        """
        Name
        ----
        `all_devices` ()

        Description
        -----------
        Get all the available devices with their state and type information.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array in which each item is a list of
        device hostname, device type, device state and current running job id. For example:

        [['panda01', 'panda', 'running', 164], ['qemu01', 'qemu', 'idle', None]]
        """

        devices_list = []
        for dev in Device.objects.all():
            if not dev.is_visible_to(self.user):
                continue
            if dev.status == Device.RETIRED:
                continue
            devices_list.append(dev)

        return [list((dev.hostname, dev.device_type.name, Device.STATUS_CHOICES[dev.status][1].lower(), dev.current_job.pk if dev.current_job else None))
                for dev in devices_list]

    def all_device_types(self):
        """
        Name
        ----
        `all_device_types` ()

        Description
        -----------
        Get all the available device types with their state and count
        information.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array in which each item is a dict
        which contains name (device type), idle, busy, offline counts.
        For example:

        [{'idle': 1, 'busy': 0, 'name': 'panda', 'offline': 0},
        {'idle': 1, 'busy': 0, 'name': 'qemu', 'offline': 0}]
        """

        device_type_names = []
        all_device_types = []
        keys = ['busy', 'name', 'idle', 'offline']

        for dev_type in DeviceType.objects.all():
            if len(dev_type.devices_visible_to(self.user)) == 0:
                continue
            device_type_names.append(dev_type.name)

        device_types = DeviceType.objects.filter(display=True).annotate(
            idle=SumIf('device', condition='status=%s' % Device.IDLE),
            offline=SumIf('device', condition='status in (%s,%s)'
                          % (Device.OFFLINE, Device.OFFLINING)),
            busy=SumIf('device', condition='status in (%s,%s)'
                       % (Device.RUNNING, Device.RESERVED)), ).order_by('name').filter(name__in=device_type_names)

        for dev_type in device_types:
            device_type = {}
            for key in keys:
                device_type[key] = getattr(dev_type, key)
            all_device_types.append(device_type)

        return all_device_types

    def pending_jobs_by_device_type(self):
        """
        Name
        ----
        `pending_jobs_by_device_type` ()

        Description
        -----------
        Get number of pending jobs in each device type.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns a dict where the key is the device type and
        the value is the number of jobs pending in that device type.
        For example:

        {'qemu': 0, 'panda': 3}
        """

        pending_jobs_by_device = {}

        jobs_res = TestJob.objects.filter(status=TestJob.SUBMITTED)\
            .values_list('requested_device_type_id')\
            .annotate(pending_jobs=(Count('id')))
        jobs = {}
        jobs_hash = dict(jobs_res)
        for job in jobs_hash:
            if job:
                jobs[job] = jobs_hash[job]
        pending_jobs_by_device.update(jobs)

        # Get rest of the devices and put number of pending jobs as 0.
        device_types = DeviceType.objects.values_list('name', flat=True)
        for device_type in device_types:
            if device_type not in pending_jobs_by_device:
                pending_jobs_by_device[device_type] = 0

        return pending_jobs_by_device

    def job_details(self, job_id):
        """
        Name
        ----
        `job_details` (`job_id`)

        Description
        -----------
        Get the details of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC structures of job details, provided
        the user is authenticated with an username and token.
        """
        self._authenticate()
        if not job_id:
            raise xmlrpclib.Fault(400, "Bad request: TestJob id was not "
                                  "specified.")
        try:
            job = get_restricted_job(self.user, job_id)
            job.status = job.get_status_display()
        except PermissionDenied:
            raise xmlrpclib.Fault(
                401, "Permission denied for user to job %s" % job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")

        return job

    def job_status(self, job_id):
        """
        Name
        ----
        `job_status` (`job_id`)

        Description
        -----------
        Get the status of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC structures of job status with the
        following fields.
        The user is authenticated with an username and token.

        `job_status`: string
        ['Submitted'|'Running'|'Complete'|'Incomplete'|'Canceled'|'Canceling']

        `bundle_sha1`: string
        The sha1 hash code of the bundle, if it existed. Otherwise it will be
        an empty string.
        """
        self._authenticate()
        if not job_id:
            raise xmlrpclib.Fault(400, "Bad request: TestJob id was not "
                                  "specified.")
        try:
            job = get_restricted_job(self.user, job_id)
        except PermissionDenied:
            raise xmlrpclib.Fault(
                401, "Permission denied for user to job %s" % job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")

        bundle_sha1 = ""
        try:
            bundle_sha1 = job.results_link.split('/')[-2]
        except:
            pass

        job_status = {
            'job_status': job.get_status_display(),
            'bundle_sha1': bundle_sha1
        }

        return job_status

    def worker_heartbeat(self, heartbeat_data):
        """
        Name
        ----
        `worker_heartbeat` (`heartbeat_data`)

        Description
        -----------
        Pushes the heartbeat of dispatcher worker node.

        Arguments
        ---------
        `heartbeat_data`: string
            Heartbeat data extracted from dispatcher worker node.

        Return value
        ------------
        This function returns an XML-RPC boolean output, provided the user is
        authenticated with an username and token.
        """
        worker = Worker()
        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")
        if not worker.can_update(self.user):
            raise xmlrpclib.Fault(403, "Permission denied.")

        worker.update_heartbeat(heartbeat_data)
        return True

    def notify_incomplete_job(self, job_id):
        """
        Name
        ----
        `notify_incomplete_job` (`job_id`)

        Description
        -----------
        Internal call to notify the master scheduler that a job on a remote worker
        ended in the Incomplete state. This allows the master to send the
        notification emails, if any. The status of the TestJob is not altered.

        Arguments
        ---------
        The TestJob.id which ended in status Incomplete.

        Return value
        ------------
        None. The user should be authenticated with a username and token.
        """
        self._authenticate()
        if not job_id:
            raise xmlrpclib.Fault(400, "Bad request: TestJob id was not "
                                  "specified.")
        try:
            job = get_restricted_job(self.user, job_id)
        except PermissionDenied:
            raise xmlrpclib.Fault(
                401, "Permission denied for user to job %s" % job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "TestJob with id '%s' was not found." % job_id)
        job.send_summary_mails()

    def all_jobs(self):
        """
        Name
        ----
        `all_jobs` ()

        Description
        -----------
        Get submitted or running jobs.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns a XML-RPC array of submitted and running jobs with their status and
        actual device for running jobs and requested device or device type for submitted jobs and
        job sub_id for multinode jobs.
        For example:

        [[73, 'multinode-job', 'submitted', None, None, 'kvm', '72.1'],
        [72, 'multinode-job', 'submitted', None, None, 'kvm', '72.0'],
        [71, 'test-job', 'running', 'kvm01', None, None, None]]
        """

        jobs = TestJob.objects.filter(status__in=[TestJob.SUBMITTED, TestJob.RUNNING])\
            .order_by('-id')
        jobs_list = [list((job.id, job.description, TestJob.STATUS_CHOICES[job.status][1].lower(), job.actual_device, job.requested_device, job.requested_device_type, job.sub_id))
                     for job in jobs]

        return jobs_list

    def get_pipeline_device_config(self, device_hostname):
        """
        Name
        ----
        `get_pipeline_device_config` (`device_hostname`)

        Description
        -----------
        Get the pipeline device configuration for given device hostname.

        Arguments
        ---------
        `device_hostname`: string
            Device hostname for which the configuration is required.

        Return value
        ------------
        This function returns an XML-RPC binary data of output file.
        """
        if not device_hostname:
            raise xmlrpclib.Fault(400, "Bad request: Device hostname was not "
                                  "specified.")

        element = DeviceDictionary.get(device_hostname)
        if element is None:
            raise xmlrpclib.Fault(404, "Specified device not found.")

        data = devicedictionary_to_jinja2(element.parameters,
                                          element.parameters['extends'])
        string_loader = jinja2.DictLoader({'%s.yaml' % device_hostname: data})
        type_loader = jinja2.FileSystemLoader(
            [os.path.join(jinja_template_path(), 'device-types')])
        env = jinja2.Environment(loader=jinja2.ChoiceLoader([string_loader,
                                                             type_loader]),
                                 trim_blocks=True)
        template = env.get_template("%s.yaml" % device_hostname)
        device_configuration = template.render()

        # validate against the device schema
        validate_device(device_configuration)

        return xmlrpclib.Binary(device_configuration.encode('UTF-8'))
