from tempfile import mkdtemp
from lava_dispatcher.pipeline import Action


class OffsetAction(Action):

    def __init__(self):
        super(OffsetAction, self).__init__()
        self.name = "offset_action"
        self.description = "calculate offset of the image"
        self.summary = "offset calculation"

    def get_partition_offset(self, image, partno):
        cmd = 'parted %s -m -s unit b print' % image
        part_data = getoutput(cmd)
        pattern = re.compile('%d:([0-9]+)B:' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                return found.group(1)
        return 0


class LoopCheckAction(Action):

    def __init__(self):
        super(LoopCheckAction, self).__init__()
        self.name = "loop_check"
        self.description = "ensure a loop back mount operation is possible"
        self.summary = "check available loop back support"

    def run(self, connection, args=None):
        available_loops = len(glob.glob('/sys/block/loop*'))
        if available_loops <= 0:
            raise RuntimeError("Could not mount the image without loopback devices. "
                               "Is the 'loop' kernel module activated?")
        return connection


class LoopMountAction(Action):
    """
    Needs to expose the final mountpoint in the context.pipeline_data
    to allow the customise action to push any test definitions in
    without doing to consecutive (identical) mounts in the Deploy and
    again in the test shell.
    """
    # FIXME: needs to be a RetryAction

    def __int__(self):
        super(LoopMountAction, self).__init__()
        self.name = "loop_mount"
        self.description = "Mount using a loopback device and offset"
        self.summary = "loopback mount"

    def run(self, connection, args=None):
        max_repeat = 10
        allow_repeat = 1
        rc = 1
        args = ['sudo', '/sbin/losetup', '-a']
        pro = subprocess.Popen(args, stdout=PIPE, stderr=PIPE)
        mounted_loops = len(pro.communicate()[0].strip().split("\n"))
        mount_cmd = "sudo mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
        return connection


class MountAction(Action):

    def __init__(self):
        super(MountAction, self).__init__()
        self.name = "mount_action"
        self.description = "mount with offset"
        self.summary = "mount loop"

    def run(self, connection, args=None):
        # move to validate step
        if not args:
            raise RuntimeError("%s called without context as argument" % self.name)
        if isinstance(args, LavaContext):
            self.context = args
        if 'download_action' not in self.context.pipeline_data:
            raise RuntimeError("Missing download action")
        raise RuntimeError("MountAction not completed yet")  # FIXME :-)
        image = self.context.pipeline_data['download_action']['file']
        if not os.path.exists(image):
            raise RuntimeError("Not able to mount %s: file does not exist" % image)
        mntdir = mkdtemp()
        offset = get_partition_offset(image, partno)  # FIXME: add OffsetAction to pipeline and get from dynamic data

        available_loops = len(glob.glob('/sys/block/loop*'))
        if available_loops <= 0:
            raise RuntimeError("Could not mount the image without loopback devices. "
                               "Is the 'loop' kernel module activated?")
        max_repeat = 10  # FIXME: needs a RetryAction
        allow_repeat = 1
        rc = 1
        args = ['sudo', '/sbin/losetup', '-a']
        pro = subprocess.Popen(args, stdout=PIPE, stderr=PIPE)
        mounted_loops = len(pro.communicate()[0].strip().split("\n"))
        mount_cmd = "sudo mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
        while mounted_loops <= available_loops:
            rc = logging_system(mount_cmd)
            if rc == 0:
                break
            if mounted_loops == available_loops:
                logging.debug("Mount failed. %d of %d loopback devices already mounted. %d of %d attempts." %
                              (mounted_loops, available_loops, allow_repeat, max_repeat))
            if allow_repeat >= max_repeat:
                raise RuntimeError("Could not mount %s after %d attempts." % (image, max_repeat))
            time.sleep(10)
            allow_repeat += 1
            pro = subprocess.Popen(args, stdout=PIPE, stderr=PIPE)
            mounted_loops = len(pro.communicate()[0].strip().split("\n"))
        if rc != 0:
            os.rmdir(mntdir)
            raise RuntimeError("Unable to mount image %s at offset %s" % (
                image, offset))
        return connection


class CustomisationAction(Action):

    def __init__(self):
        super(CustomisationAction, self).__init__()
        self.name = "customise"
        self.description = "customise image during deployment"
        self.summary = "customise image"

    def run(self, connection, args=None):
        return connection


class UnmountAction(Action):

    def __init__(self):
        super(UnmountAction, self).__init__()
        self.name = "umount"
        self.description = "unmount the test image at end of deployment"
        self.summary = "unmount image"

    def run(self, connection, args=None):
        logging_system('sudo umount ' + mntdir)
        logging_system('rm -rf ' + mntdir)
        return connection
