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
