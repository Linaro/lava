# Deploy action

The deploy actions are deploying the provided software on the DUT using the
method specified in the job definition.

## Artifacts

In the deploy action, the following parameters are available for artifacts
downloads:

* archive
* checksums
* compression
* headers
* url

### Archive

When specifying `archive: tar`, LAVA will extract the tar archive prior to
using it.

```yaml
- deploy:
    images:
      boot:
        url: http://example.com/boot.tar.xz
        compression: xz
        archive: tar
```

### Checksums

LAVA is able to compute the checksums of the download
artifacts using `md5sum`, `sha256sum` and `sha512sum`:

```yaml
- deploy:
    tmpfs:
      rootfs:
        url: http://example.com/rootfs.img.xz
        compression: xz
        md5sum: d8784b27867b3dcad90cbea66eacc264
```

!!! info "Multiple checksums"
    If needed, you can provide multiple checksum algorithms for the same
    artifact.

### Compression

If needed, LAVA can uncompress a compressed artifact by specifying
`compression`.

```yaml
- deploy:
    tmpfs:
      rootfs:
        url: http://example.com/rootfs.img.xz
        compression: xz
```

The supported formats are: `bz2`, `gz`, `xz`, `zip` or `zstd`.

### Headers

For http(s) artifacts, you can provide additional headers:

```yaml
- deploy:
    tmpfs:
      rootfs:
        url: http://example.com/rootfs.img.xz
        compression: xz
        headers:
          my-header1: value
```

### URL

Specifies the URL to download.

URLs **must** use one of the supported protocols:

* `http://`
* `https://`
* `file://`
* `scp://`
* `downloads://`

URLs are checked during the test job validation to ensure that the file can be
downloaded. Missing files will cause the test job to end as `Incomplete`.

URLs allow placeholders for all supported protocols.

```yaml
- deploy:
    to: tftp
    kernel:
      url: http://{FILE_SERVER_IP}/linux/Image-imx8mmevk.bin
      type: image
    persistent_nfs:
      address: "{FILE_SERVER_IP}:/var/lib/lava/dispatcher/tmp/linux/imx8mm_rootfs"
    dtb:
      url: http://{FILE_SERVER_IP}/linux/imx8mm-evk.dtb
    os: debian
```

!!! note
    Admin can define any placeholder and assign an address to it in device
    dictionary. LAVA then substitutes the placeholders in job with the
    `static_info` to generate a new `url`.

```jinja
{% set static_info = [{'FILE_SERVER_IP': "10.192.244.104"}] %}
```

## Overlays

LAVA can apply a set of overlays to every artifact. The configuration should
look like:

```yaml
- deploy:
    tmpfs:
      rootfs:
        url: http://example.com/rootfs.img.xz
        compression: xz
        format: ext4
        overlays:
          lava: true
          kselftest:
            url: https://exampl.com/kselftes.tar.xz
            compression: xz
            format: tar
            path: /
```

You should provide:

* `format`: the format of the artifact to update (`cpio.newc`, `ext4` or `tar`)
* `overlays`: a dictionary of overlays to insert

You can also provide:

* `partition`: to update a given partition (for `ext4` with multiple partitions)
* `sparse`: set to `true` if the artifact is a sparse image

### LAVA overlay

In order to insert the LAVA overlay (that include the test definitions and
helpers), use `lava: true` as overlay.

### Overlays

You can insert a tar archive or a file in the artifact. You should provide:

* `format`: the format of the overlay (`file` or `tar`).
* `path`: the path in the artifact
