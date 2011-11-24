from commands import getstatusoutput
import logging
import os
from tempfile import mkdtemp

from lava_dispatcher.utils import download, download_with_cache


def _generate_image(client, hwpack_url, rootfs_url, use_cache=True):
    """Generate image from a hwpack and rootfs url

    :param hwpack_url: url of the Linaro hwpack to download
    :param rootfs_url: url of the Linaro image to download
    """
    lava_cachedir = client.context.lava_cachedir
    LAVA_IMAGE_TMPDIR = client.context.lava_image_tmpdir
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
