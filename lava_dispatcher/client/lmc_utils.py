from commands import getoutput, getstatusoutput
import contextlib
import logging
import re
import os
import shutil
from tempfile import mkdtemp

from lava_dispatcher.client.base import CriticalError
from lava_dispatcher.utils import (
    download,
    download_with_cache,
    logging_system,
    )

def refresh_hwpack(client, kernel_matrix, hwpack, use_cache=True):
    lava_cachedir = client.context.lava_cachedir
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


def generate_image(client, hwpack_url, rootfs_url, kernel_matrix, use_cache=True):
    """Generate image from a hwpack and rootfs url

    :param hwpack_url: url of the Linaro hwpack to download
    :param rootfs_url: url of the Linaro image to download
    """
    lava_cachedir = client.context.lava_cachedir
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
    metadata = client.context.test_data.get_metadata()
    metadata['target.linaro-media-create-version'] = output
    client.context.test_data.add_metadata(metadata)

    image_file = os.path.join(tarball_dir, "lava.img")
    #XXX Hack for removing startupfiles from snowball hwpacks
    if client.device_type == "snowball_sd":
        cmd = "sudo linaro-hwpack-replace -r startupfiles-v3 -t %s -i" % hwpack_path
        rc, output = getstatusoutput(cmd)
        if rc:
            raise RuntimeError("linaro-hwpack-replace failed: %s" % output)

    cmd = ("sudo flock /var/lock/lava-lmc.lck linaro-media-create --hwpack-force-yes --dev %s "
           "--image-file %s --binary %s --hwpack %s --image-size 3G" %
           (client.lmc_dev_arg, image_file, rootfs_path, hwpack_path))
    logging.info("Executing the linaro-media-create command")
    logging.info(cmd)
    rc, output = getstatusoutput(cmd)
    if rc:
        client.rmtree(tarball_dir)
        raise RuntimeError("linaro-media-create failed: %s" % output)
    return image_file

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
