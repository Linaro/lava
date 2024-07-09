# Downloads

## Downloads deploy

Download the given images and allow to post-process the images.

```yaml
actions:
- deploy:
    to: downloads
    images:
      rootfs:
        url: https://example.com/rootfs.img.xz
        compression: xz
```

## Post-processing

The `downloads` deploy action allows to run a custom post-processing script. The configuration would look like the following:

```yaml
actions:
- deploy:
    to: downloads
    images:
      rootfs:
        url: https://example.com/sid.img.xz
        compression: xz
    postprocess:
      docker:
        image: debian
        steps:
        - cp rootfs/sid.img rootfs/sid-modified.img
        - ls -lhR
```

The post-processing `steps` are ran inside the provided docker container. The
artefacts will be in sub-directories of the working directory. The name of
the sub-directories are the keys of the `images` dictionary (`rootfs` in the
example).

!!! info "Using the artefacts"
    In subsequent deploy actions, you can use the artefacts created by the
    postprocessing step with `downloads://sid-modified.img`.

### LAVA overlay

LAVA overlay is prepared when there is a test action available in the job.
In some cases LAVA is able to add overlay to image as part of the download
process. As this is not always the case, it is useful to have access to
overlay tarball in the postprocessing step. The file is available in the
`downloads` directory. The file name isn't constant as it depends on the
test job definition structure. Example file name can look like:

    overlay-1.1.5.tar.gz

It always starts with `overlay` and ends with `.tar.gz`. The middle part
depends is the ID of the action in the LAVA job definition and will be different
for different job definitions.

Example use of overlay in the postprocessing step can be adding it to the ramdisk

```yaml
- deploy:
    images:
      image:
        url: 'https://example.com/Image'
      dtb:
        url: 'https://example.com/device.dtb'
      ramdisk:
        url: 'https://example.com/ramdisk.gz'
    timeout:
      minutes: 5
    to: downloads
    postprocess:
      docker:
        image: mkbootimage:master
        steps:
        - mkdir lava_overlay
        - tar xvf overlay*.tar.gz -C lava_overlay
        - "(cd lava_overlay ; find * | cpio -o -H newc -R +0:+0 | gzip -9 >> ../ramdisk.gz)"
        - mkbootimg --header_version 2 --kernel Image --dtb device.dtb --cmdline "earlycon clk_ignore_unused pd_ignore_unused audit=0" --ramdisk ramdisk.gz --output boot.img
```
