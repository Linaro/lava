# Deploy action

The deploy actions are deploying the provided software on the DUT using the
method specified in the job definition.

## Artifacts

In the deploy action, the following parameters are available for artefacts
downloads:

* archive
* checksums
* compression
* headers
* protocole

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

### Protocole

When downloading an artifact, LAVA supports the following protocols: `http`,
`https`, `file` and `lxc`.

## Overlays

LAVA can apply a set of overlays to every artefacts. The configuration should
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

* `format`: the format of the artefact to update (`cpio.newc`, `ext4` or `tar`)
* `overlays`: a dictionary of overlays to insert

You can also provide:

* `partition`: to update a given partition (for `ext4` with multiple partitions)
* `sparse`: set to `true` if the artefact is a sparse image 

### LAVA overlay

In order to insert the LAVA overlay (that include the test definitions and
helpers), use `lava: true` as overlay.

### Overlays

You can insert a tar archive or a file in the artefact. You should provide:

* `format`: the format of the overlay (`file` or `tar`).
* `path`: the path in the artefact
