import xmlrpclib
from simplejson import JSONDecodeError
from django.db.models import Count
from linaro_django_xmlrpc.models import ExposedAPI
from lava_scheduler_app.models import (
    Device,
    DeviceType,
    JSONDataError,
    TestJob,
    )
from lava_scheduler_app.views import (
    SumIfSQL,
    SumIf
)


class SchedulerAPI(ExposedAPI):

    def submit_job(self, job_data):
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
        return job.id

    def resubmit_job(self, job_id):
        try:
            job = TestJob.objects.accessible_by_principal(self.user).get(pk=job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")
        return self.submit_job(job.definition)

    def cancel_job(self, job_id):
        if not self.user:
            raise xmlrpclib.Fault(401, "Authentication required.")
        job = TestJob.objects.get(pk=job_id)
        if not job.can_cancel(self.user):
            raise xmlrpclib.Fault(403, "Permission denied.")
        job.cancel()
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
            job = TestJob.objects.accessible_by_principal(self.user).get(
                pk=job_id)
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
            offline=SumIf('device', condition='status in (%s,%s)' % (
                    Device.OFFLINE, Device.OFFLINING)),
            busy=SumIf('device', condition='status=%s' % Device.RUNNING),
            ).order_by('name')

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

        jobs = TestJob.objects.filter(status=TestJob.SUBMITTED).values_list(
            'requested_device_type_id').annotate(
            pending_jobs=(Count('id')))
        pending_jobs_by_device.update(dict(jobs))

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
            job = TestJob.objects.accessible_by_principal(self.user).get(
                pk=job_id)
        except TestJob.DoesNotExist:
            raise xmlrpclib.Fault(404, "Specified job not found.")

        return job

    def job_status(self, job_id):
        """
        Name
        ----
        `job_statuss` (`job_id`)

        Description
        -----------
        Get the status of given job id.

        Arguments
        ---------
        `job_id`: string
            Job id for which the output is required.

        Return value
        ------------
        This function returns an XML-RPC structures of job status and bundle sha1, if exists, otherwise it will be an empty string, provided
        the user is authenticated with an username and token.
        """

        if not self.user:
            raise xmlrpclib.Fault(
                401, "Authentication with user and token required for this "
                "API.")

        try:
            job = TestJob.objects.accessible_by_principal(self.user).get(
                pk=job_id)
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

