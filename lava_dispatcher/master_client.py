
from commands import getoutput, getstatusoutput
import contextlib
import os
import pexpect
import re
import shutil
import traceback
from tempfile import mkdtemp
import logging

from lava_dispatcher.utils import download, download_with_cache
from lava_dispatcher.client import (
    CommandRunner,
    CriticalError,
    LavaClient,
    NetworkCommandRunner,
    OperationFailed,
    )


def _extract_partition(image, offset, tarfile):
    """Mount a partition and produce a tarball of it

    :param image: The image to mount
    :param offset: offset of the partition, as a string
    :param tarfile: path and filename of the tgz to output
    """
    error_msg = None
    mntdir = mkdtemp()
    cmd = "sudo mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
    rc, output = getstatusoutput(cmd)
    if rc:
        os.rmdir(mntdir)
        raise RuntimeError("Unable to mount image %s at offset %s" % (
            image, offset))
    cmd = "sudo tar -C %s -czf %s ." % (mntdir, tarfile)
    rc, output = getstatusoutput(cmd)
    if rc:
        error_msg = "Failed to create tarball: %s" % tarfile
    cmd = "sudo umount %s" % mntdir
    rc, output = getstatusoutput(cmd)
    os.rmdir(mntdir)
    if error_msg:
        raise RuntimeError(error_msg)

def _deploy_linaro_rootfs(session, rootfs):
    logging.info("Deploying linaro image")
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/root')
    session.run('mount /dev/disk/by-label/testrootfs /mnt/root')
    rc = session.run(
        'wget -qO- %s |tar --numeric-owner -C /mnt/root -xzf -' % rootfs,
        timeout=3600)
    if rc != 0:
        msg = "Deploy test rootfs partition: failed to download tarball."
        raise OperationFailed(msg)

    session.run('echo linaro > /mnt/root/etc/hostname')
    #DO NOT REMOVE - diverting flash-kernel and linking it to /bin/true
    #prevents a serious problem where packages getting installed that
    #call flash-kernel can update the kernel on the master image
    session.run(
        'chroot /mnt/root dpkg-divert --local /usr/sbin/flash-kernel')
    session.run(
        'chroot /mnt/root ln -sf /bin/true /usr/sbin/flash-kernel')
    session.run('umount /mnt/root')

def _deploy_linaro_bootfs(session, bootfs):
    logging.info("Deploying linaro bootfs")
    session.run('udevadm trigger')
    session.run('mkdir -p /mnt/boot')
    session.run('mount /dev/disk/by-label/testboot /mnt/boot')
    rc = session.run(
        'wget -qO- %s |tar --numeric-owner -C /mnt/boot -xzf -' % bootfs)
    if rc != 0:
        msg = "Deploy test boot partition: failed to download tarball."
        raise OperationFailed(msg)
    session.run('umount /mnt/boot')


class PrefixCommandRunner(CommandRunner):
    """A CommandRunner that prefixes every command run with a given string.

    The motivating use case is to prefix every command with 'chroot
    $LOCATION'.
    """

    def __init__(self, prefix, connection, prompt_str):
        super(PrefixCommandRunner, self).__init__(connection, prompt_str)
        if not prefix.endswith(' '):
            prefix += ' '
        self._prefix = prefix

    def run(self, cmd, response=None, timeout=-1):
        return super(PrefixCommandRunner, self).run(self._prefix + cmd)

class MasterCommandRunner(NetworkCommandRunner):
    """A CommandRunner to use when the board is booted into the master image.

    See `LavaClient.master_session`.
    """

    def __init__(self, client):
        super(MasterCommandRunner, self).__init__(client, client.master_str)

    def get_master_ip(self):
        #get master image ip address
        try:
            self.wait_network_up()
        except:
            logging.warning(traceback.format_exc())
            return None
        #tty device uses minimal match, see pexpect wiki
        #pattern1 = ".*\n(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
        pattern1 = "(\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?\.\d?\d?\d?)"
        cmd = ("ifconfig %s | grep 'inet addr' | awk -F: '{print $2}' |"
                "awk '{print $1}'" % self._client.default_network_interface)
        self.run(
            cmd, [pattern1, pexpect.EOF, pexpect.TIMEOUT], timeout=5)
        if self.match_id == 0:
            logging.info("\nmatching pattern is %s" % self.match_id)
            ip = self.match.groups()[0]
            logging.info("Master IP is %s" % ip)
            return ip
        return None


class LavaMasterImageClient(LavaClient):

    @property
    def master_str(self):
        return self.device_option("MASTER_STR")

    def deploy_linaro(self, hwpack, rootfs, kernel_matrix=None, use_cache=True):
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        LAVA_IMAGE_URL = self.context.lava_image_url
        logging.info("deploying on %s" % self.hostname)
        logging.info("  hwpack: %s" % hwpack)
        logging.info("  rootfs: %s" % rootfs)
        if kernel_matrix:
            logging.info("  package: %s" % kernel_matrix[0])
        logging.info("Booting master image")
        self._boot_master_image()
        with self._master_session() as session:
            self._format_testpartition(session)

            logging.info("Waiting for network to come up")
            try:
                session.wait_network_up()
            except:
                tb = traceback.format_exc()
                self.sio.write(tb)
                raise CriticalError("Unable to reach LAVA server, check network")

            if kernel_matrix:
                hwpack = self._refresh_hwpack(kernel_matrix, hwpack, use_cache)
                #make new hwpack downloadable
                hwpack = hwpack.replace(LAVA_IMAGE_TMPDIR, '')
                hwpack = '/'.join(u.strip('/') for u in [
                    LAVA_IMAGE_URL, hwpack])
                logging.info("  hwpack with new kernel: %s" % hwpack)

            logging.info("About to handle with the build")
            try:
                boot_tgz, root_tgz = self._generate_tarballs(hwpack, rootfs,
                    use_cache)
            except:
                tb = traceback.format_exc()
                self.sio.write(tb)
                raise CriticalError("Deployment tarballs preparation failed")
            boot_tarball = boot_tgz.replace(LAVA_IMAGE_TMPDIR, '')
            root_tarball = root_tgz.replace(LAVA_IMAGE_TMPDIR, '')
            boot_url = '/'.join(u.strip('/') for u in [
                LAVA_IMAGE_URL, boot_tarball])
            root_url = '/'.join(u.strip('/') for u in [
                LAVA_IMAGE_URL, root_tarball])
            try:
                _deploy_linaro_rootfs(session, root_url)
                _deploy_linaro_bootfs(session, boot_url)
            except:
                tb = traceback.format_exc()
                self.sio.write(tb)
                raise CriticalError("Deployment failed")
            finally:
                shutil.rmtree(self.tarball_dir)

    def _boot_master_image(self):
        """
        reboot the system, and check that we are in a master shell
        """
        self.proc.soft_reboot()
        try:
            self.proc.expect("Starting kernel")
            self._in_master_shell(120)
        except:
            logging.exception("in_master_shell failed")
            self.proc.hard_reboot()
            self._in_master_shell(300)
        self.proc.sendline('export PS1="$PS1 [rc=$(echo \$?)]: "')
        self.proc.expect(self.master_str, timeout=10)

    def _format_testpartition(self, session):
        logging.info("Format testboot and testrootfs partitions")
        session.run('umount /dev/disk/by-label/testrootfs')
        session.run(
            'mkfs.ext3 -q /dev/disk/by-label/testrootfs -L testrootfs')
        session.run('umount /dev/disk/by-label/testboot')
        session.run('mkfs.vfat /dev/disk/by-label/testboot -n testboot')

    def _get_partition_offset(self, image, partno):
        cmd = 'parted %s -m -s unit b print' % image
        part_data = getoutput(cmd)
        pattern = re.compile('%d:([0-9]+)B:' % partno)
        for line in part_data.splitlines():
            found = re.match(pattern, line)
            if found:
                return found.group(1)
        return None

    def _generate_tarballs(self, hwpack_url, rootfs_url, use_cache=True):
        """Generate tarballs from a hwpack and rootfs url

        :param hwpack_url: url of the Linaro hwpack to download
        :param rootfs_url: url of the Linaro image to download
        """
        lava_cachedir = self.context.lava_cachedir
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        self.tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        tarball_dir = self.tarball_dir
        os.chmod(tarball_dir, 0755)
        #fix me: if url is not http-prefix, copy it to tarball_dir
        if use_cache:
            logging.info("Downloading the %s file using cache" % hwpack_url)
            hwpack_path = download_with_cache(hwpack_url, tarball_dir, lava_cachedir)

            logging.info("Downloading the %s file using cache" % rootfs_url)
            rootfs_path = download_with_cache(rootfs_url, tarball_dir, lava_cachedir)
        else:
            logging.info("Downloading the %s file" % hwpack_url)
            hwpack_path = download(hwpack_url, tarball_dir)

            logging.info("Downloading the %s file" % rootfs_url)
            rootfs_path = download(rootfs_url, tarball_dir)

        logging.info("linaro-media-create version information")
        cmd = "sudo linaro-media-create -v"
        rc, output = getstatusoutput(cmd)
        metadata = self.context.test_data.get_metadata()
        metadata['target.linaro-media-create-version'] = output
        self.context.test_data.add_metadata(metadata)

        image_file = os.path.join(tarball_dir, "lava.img")
        #XXX Hack for removing startupfiles from snowball hwpacks
        if self.device_type == "snowball_sd":
            cmd = "sudo linaro-hwpack-replace -r startupfiles-v3 -t %s -i" % hwpack_path
            rc, output = getstatusoutput(cmd)
            if rc:
                raise RuntimeError("linaro-hwpack-replace failed: %s" % output)

        cmd = ("sudo flock /var/lock/lava-lmc.lck linaro-media-create --hwpack-force-yes --dev %s "
               "--image-file %s --binary %s --hwpack %s --image-size 3G" %
               (self.lmc_dev_arg, image_file, rootfs_path, hwpack_path))
        logging.info("Executing the linaro-media-create command")
        logging.info(cmd)
        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise RuntimeError("linaro-media-create failed: %s" % output)
        boot_offset = self._get_partition_offset(image_file, self.boot_part)
        root_offset = self._get_partition_offset(image_file, self.root_part)
        boot_tgz = os.path.join(tarball_dir, "boot.tgz")
        root_tgz = os.path.join(tarball_dir, "root.tgz")
        try:
            _extract_partition(image_file, boot_offset, boot_tgz)
            _extract_partition(image_file, root_offset, root_tgz)
        except:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise
        return boot_tgz, root_tgz

    def _refresh_hwpack(self, kernel_matrix, hwpack, use_cache=True):
        lava_cachedir = self.context.lava_cachedir
        LAVA_IMAGE_TMPDIR = self.context.lava_image_tmpdir
        logging.info("Deploying new kernel")
        new_kernel = kernel_matrix[0]
        deb_prefix = kernel_matrix[1]
        filesuffix = new_kernel.split(".")[-1]

        if filesuffix != "deb":
            raise CriticalError("New kernel only support deb kernel package!")

        # download package to local
        tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
        os.chmod(tarball_dir, 0755)
        if use_cache:
            kernel_path = download_with_cache(new_kernel, tarball_dir, lava_cachedir)
            hwpack_path = download_with_cache(hwpack, tarball_dir, lava_cachedir)
        else:
            kernel_path = download(new_kernel, tarball_dir)
            hwpack_path = download(hwpack, tarball_dir)

        cmd = ("sudo linaro-hwpack-replace -t %s -p %s -r %s"
                % (hwpack_path, kernel_path, deb_prefix))

        rc, output = getstatusoutput(cmd)
        if rc:
            shutil.rmtree(tarball_dir)
            tb = traceback.format_exc()
            self.sio.write(tb)
            raise RuntimeError("linaro-hwpack-replace failed: %s" % output)

        #fix it:l-h-r doesn't make a output option to specify the output hwpack,
        #so it needs to do manually here

        #remove old hwpack and leave only new hwpack in tarball_dir
        os.remove(hwpack_path)
        hwpack_list = os.listdir(tarball_dir)
        for hp in hwpack_list:
            if hp.split(".")[-1] == "gz":
                new_hwpack_path = os.path.join(tarball_dir, hp)
                return new_hwpack_path

    def deploy_linaro_android(self, *args):
        pass

    def reliable_session(self):
        return self._partition_session('testrootfs')

    @contextlib.contextmanager
    def _partition_session(self, partition):
        """A session that can be used to run commands in a given test
        partition.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        with self._master_session() as master_session:
            directory = '/mnt/' + partition
            master_session.run('mkdir -p %s' % directory)
            master_session.run('mount /dev/disk/by-label/%s %s' % (partition, directory))
            master_session.run(
                'cp -f %s/etc/resolv.conf %s/etc/resolv.conf.bak' % (
                    directory, directory))
            master_session.run('cp -L /etc/resolv.conf %s/etc' % directory)
            #eliminate warning: Can not write log, openpty() failed
            #                   (/dev/pts not mounted?), does not work
            master_session.run('mount --rbind /dev %s/dev' % directory)
            try:
                yield PrefixCommandRunner(
                    'chroot ' + directory, self.proc, self.master_str)
            finally:
                master_session.run(
                    'cp -f %s/etc/resolv.conf.bak %s/etc/resolv.conf' % (
                        directory, directory))
                cmd = ('cat /proc/mounts | awk \'{print $2}\' | grep "^%s/dev"'
                       '| sort -r | xargs umount' % directory)
                master_session.run(cmd)
                master_session.run('umount ' + directory)

    def _in_master_shell(self, timeout=10):
        """
        Check that we are in a shell on the master image
        """
        self.proc.sendline("")
        match_id = self.proc.expect(
            [self.master_str, pexpect.TIMEOUT], timeout=timeout)
        if match_id == 1:
            raise OperationFailed
        logging.info("System is in master image now")

    @contextlib.contextmanager
    def _master_session(self):
        """A session that can be used to run commands in the master image.

        Anything that uses this will have to be done differently for images
        that are not deployed via a master image (e.g. using a JTAG to blow
        the image onto the card or testing under QEMU).
        """
        try:
            self._in_master_shell()
        except OperationFailed:
            self._boot_master_image()
        yield MasterCommandRunner(self)
