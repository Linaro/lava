from commands import getoutput, getstatusoutput
import contextlib
import logging
import pexpect
import re
import os
import shutil
from tempfile import mkdtemp
import sys
import time

from lava_dispatcher.client.base import CriticalError
from lava_dispatcher.utils import (
    download,
    logging_system,
    )

def refresh_hwpack(client, kernel_matrix, hwpack, use_cache=True):
    lava_proxy = client.context.lava_proxy
    LAVA_IMAGE_TMPDIR = client.context.lava_image_tmpdir
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
        proxy = lava_proxy
    else:
        proxy = None
    kernel_path = download(new_kernel, tarball_dir, proxy)
    hwpack_path = download(hwpack, tarball_dir, proxy)

    cmd = ("sudo linaro-hwpack-replace -t %s -p %s -r %s"
            % (hwpack_path, kernel_path, deb_prefix))

    rc, output = getstatusoutput(cmd)
    if rc:
        shutil.rmtree(tarball_dir)
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


def generate_image(client, hwpack_url, rootfs_url, kernel_matrix, use_cache=True, rootfstype=None):
    """Generate image from a hwpack and rootfs url

    :param hwpack_url: url of the Linaro hwpack to download
    :param rootfs_url: url of the Linaro image to download
    """
    lava_proxy = client.context.lava_proxy
    LAVA_IMAGE_TMPDIR = client.context.lava_image_tmpdir
    LAVA_IMAGE_URL = client.context.lava_image_url
    logging.info("preparing to deploy on %s" % client.hostname)
    logging.info("  hwpack: %s" % hwpack_url)
    logging.info("  rootfs: %s" % rootfs_url)
    if kernel_matrix:
        logging.info("  package: %s" % kernel_matrix[0])
        hwpack_url = refresh_hwpack(kernel_matrix, hwpack_url, use_cache)
        #make new hwpack downloadable
        hwpack_url = hwpack_url.replace(LAVA_IMAGE_TMPDIR, '')
        hwpack_url = '/'.join(u.strip('/') for u in [
            LAVA_IMAGE_URL, hwpack_url])
        logging.info("  hwpack with new kernel: %s" % hwpack_url)
    tarball_dir = mkdtemp(dir=LAVA_IMAGE_TMPDIR)
    os.chmod(tarball_dir, 0755)
    #fix me: if url is not http-prefix, copy it to tarball_dir
    if use_cache:
        proxy = lava_proxy
    else:
        proxy = None

    logging.info("Downloading the %s file" % hwpack_url)
    hwpack_path = download(hwpack_url, tarball_dir, proxy)

    logging.info("Downloading the %s file" % rootfs_url)
    rootfs_path = download(rootfs_url, tarball_dir, proxy)

    logging.info("linaro-media-create version information")
    cmd = "sudo linaro-media-create -v"
    rc, output = getstatusoutput(cmd)
    metadata = client.context.test_data.get_metadata()
    metadata['target.linaro-media-create-version'] = output
    client.context.test_data.add_metadata(metadata)

    image_file = os.path.join(tarball_dir, "lava.img")

    logging.info("client.device_type = %s" %client.device_type)

    cmd = ("sudo flock /var/lock/lava-lmc.lck linaro-media-create --hwpack-force-yes --dev %s "
           "--image-file %s --binary %s --hwpack %s --image-size 3G" %
           (client.lmc_dev_arg, image_file, rootfs_path, hwpack_path))
    if rootfstype is not None:
        cmd += ' --rootfs ' + rootfstype
    logging.info("Executing the linaro-media-create command")
    logging.info(cmd)
    try:
        _run_linaro_media_create(cmd)
    except:
        shutil.rmtree(tarball_dir)
        raise
    return image_file

def generate_android_image(device, boot, data, system, ofile, size="2000M"):
    cmd = ("sudo flock /var/lock/lava-lmc.lck linaro-android-media-create "
           "--dev %s --image_file %s --image_size %s "
           "--boot %s --userdata %s --system %s" %
            (device, ofile, size, boot, data,system) )
    logging.info("Generating android image with: %s" % cmd)
    _run_linaro_media_create(cmd)

def get_partition_offset(image, partno):
    cmd = 'parted %s -m -s unit b print' % image
    part_data = getoutput(cmd)
    pattern = re.compile('%d:([0-9]+)B:' % partno)
    for line in part_data.splitlines():
        found = re.match(pattern, line)
        if found:
            return found.group(1)
    return None


@contextlib.contextmanager
def image_partition_mounted(image_file, partno):
    mntdir = mkdtemp()
    image = image_file
    offset = get_partition_offset(image, partno)
    mount_cmd = "sudo mount -o loop,offset=%s %s %s" % (offset, image, mntdir)
    rc = logging_system(mount_cmd)
    if rc != 0:
        os.rmdir(mntdir)
        raise RuntimeError("Unable to mount image %s at offset %s" % (
            image, offset))
    try:
        yield mntdir
    finally:
        logging_system('sudo umount ' + mntdir)
        logging_system('rm -rf ' + mntdir)

def _run_linaro_media_create(cmd):
    """Run linaro-media-create and accept licenses thrown up in the process.
    """
    proc = pexpect.spawn(cmd, logfile=sys.stdout)

    # This code is a bit out of control.  It describes a state machine.  Each
    # state has a name, a mapping patterns to wait for -> state to move to, a
    # timeout for how long to wait for said pattern and optionally some input
    # to send to l-m-c when you enter the step.

    # The basic outline is this:

    # We wait for l-m-c to actually start.  This has an enormous timeout,
    # because 'cmd' starts with 'flock /var/lock/lava-lmc.lck' and when lots
    # of jobs start at the same time, it can be a long time before the lock is
    # acquired.

    # Once its going, we watch for a couple of key phrases that suggets a
    # license popup has appeared.  The next few states navigate through the
    # dialogs and then accept the license.  The 'say-yes' state has extra fun
    # stuff to try to move to a state where the "<Ok>" button is highlighted
    # before pressing space (the acceptance dialogs are not consistent about
    # whether <Ok> is the default or not!).

    states = {
        'waiting': {
            'expectations': {
                "linaro-hwpack-install": 'default',
                },
            'timeout': 86400,
            },
        'default': {
            'expectations': {
                "TI TSPA Software License Agreement": 'accept-tspa',
                "SNOWBALL CLICK-WRAP": 'accept-snowball',
                "LIMITED LICENSE AGREEMENT FOR APPLICATION  DEVELOPERS": 'accept-snowball',
                },
            'timeout': 3600,
            },
        'accept-tspa': {
            'expectations': {"<Ok>": 'accept-tspa-1'},
            'timeout': 1,
            },
        'accept-tspa-1': {
            'input': "\t ",
            'expectations': {
                "Accept TI TSPA Software License Agreement": 'say-yes',
                },
            'timeout': 1,
            },
        'say-yes': {
            'expectations': {
                "  <(Yes|Ok)>": 'say-yes-tab',
                "\\033\[41m<(Yes|Ok)>": 'say-yes-space',
                },
            'timeout': 1,
            },
        'say-yes-tab': {
            'input': "\t",
            'expectations': {
                ".": 'say-yes',
                },
            'timeout': 1,
            },
        'say-yes-space': {
            'input': " ",
            'expectations': {
                ".": 'default',
                },
            'timeout': 1,
            },
        'accept-snowball': {
            'expectations': {"<Ok>": 'accept-snowball-1'},
            'timeout': 1,
            },
        'accept-snowball-1': {
            'input': "\t ",
            'expectations': {
                "Do you accept": 'say-yes',
                },
            'timeout': 1,
            },
        }


    state = 'waiting'

    while True:
        state_data = states[state]
        patterns = []
        next_state_names = []
        if 'input' in state_data:
            proc.send(state_data['input'])
        for pattern, next_state in state_data['expectations'].items():
            patterns.append(pattern)
            next_state_names.append(next_state)
        patterns.append(pexpect.EOF)
        next_state_names.append(None)
        logging.debug('waiting for %r' % patterns)
        match_id = proc.expect(patterns, timeout=state_data['timeout'])
        state = next_state_names[match_id]
        if state is None:
            return
