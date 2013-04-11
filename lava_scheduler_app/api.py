import xmlrpclib
from simplejson import JSONDecodeError
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
        This function returns an XML-RPC binary data of output file.
        """

        job = TestJob.objects.get(pk=job_id)
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

        [['qemu01', 'qemu', 'Idle'], ['panda01', 'panda', 'Idle']]
        """

        device_list = []
        devices = Device.objects.all()
        for device in devices:
            device_list.append((device.hostname,
                                device.device_type.name,
                                Device.STATUS_CHOICES[device.status][1]))

        return device_list

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

    def pending_jobs(self):
        """
        Name
        ----
        `pending_jobs` ()

        Description
        -----------
        Get all pending jobs, with device type information.

        Arguments
        ---------
        None

        Return value
        ------------
        This function returns an XML-RPC array in which each item is a list
        which contains job id and requested device type.
        For example:

        [[22, 'panda'], [23, 'panda'], [24, 'panda'], [25, 'panda']]
        """
        job_list = []

        jobs = TestJob.objects.all()

        for job in jobs:
            if job.status == 0:
                job_list.append((job.id, job.requested_device_type_id))

        return job_list
