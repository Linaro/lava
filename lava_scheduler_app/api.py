import xmlrpclib
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
)
from lava_scheduler_app.views import (
    SumIf,
    get_restricted_job
)


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
        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")
        if not self.user.has_perm('lava_scheduler_app.add_testjob'):
            raise xmlrpclib.Fault(
                403, "Permission denied.  User %r does not have the "
                "'lava_scheduler_app.add_testjob' permission.  Contact "
                "the administrators." % self.user.username)
        try:
            job = TestJob.from_json_and_user(job_data, self.user)
        except JSONDecodeError as e:
            raise xmlrpclib.Fault(400, "Decoding JSON failed: %s." % e)
        except (JSONDataError, ValueError) as e:
            raise xmlrpclib.Fault(400, str(e))
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
        if not self.user:
            raise xmlrpclib.Fault(401, "Authentication required.")
        try:
            job = get_restricted_job(self.user, job_id)
        except PermissionDenied:
            raise xmlrpclib.Fault(403, "Permission denied")
        if not job.can_cancel(self.user):
            raise xmlrpclib.Fault(403, "Permission denied.")
        if job.is_multinode:
            for multinode_job in job.sub_jobs_list:
                multinode_job.cancel(self.user)
        elif job.is_vmgroup:
            for vmgroup_job in job.sub_jobs_list:
                vmgroup_job.cancel(self.user)
        else:
            job.cancel(self.user)
        return True

    def job_output(self, job_id):
        """
        Name
        ----
        `job_output` (`job_id`)

        Description
        -----------
        Get the output of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC binary data of output file, provided
        the user is authenticated with an username and token.
        """

        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")

        try:
            job = get_restricted_job(self.user, job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")

        return xmlrpclib.Binary(job.output_file().read())

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
        device hostname, device type and device state. For example:

        [['panda01', 'panda', 'running'], ['qemu01', 'qemu', 'idle']]
        """

        devices = Device.objects.values_list('hostname',
                                             'device_type__name',
                                             'status')
        devices = [list((x[0], x[1], Device.STATUS_CHOICES[x[2]][1].lower()))
                   for x in devices]

        return devices

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

        device_type_list = []
        keys = ['busy', 'name', 'idle', 'offline']

        device_types = DeviceType.objects.filter(display=True).annotate(
            idle=SumIf('device', condition='status=%s' % Device.IDLE),
            offline=SumIf('device', condition='status in (%s,%s)'
                          % (Device.OFFLINE, Device.OFFLINING)),
            busy=SumIf('device', condition='status in (%s,%s)'
                       % (Device.RUNNING, Device.RESERVED)), ).order_by('name')

        for dev_type in device_types:
            device_type = {}
            for key in keys:
                device_type[key] = getattr(dev_type, key)
            device_type_list.append(device_type)

        return device_type_list

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

        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")

        try:
            job = get_restricted_job(self.user, job_id)
            job.status = job.get_status_display()
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

        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")

        try:
            job = get_restricted_job(self.user, job_id)
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
        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this API.")
        if not job_id:
            raise xmlrpclib.Fault(400, "Bad request: TestJob id was not specified.")
        try:
            job = get_restricted_job(self.user, job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "TestJob with id '%s' was not found." % job_id)
        job.send_summary_mails()
