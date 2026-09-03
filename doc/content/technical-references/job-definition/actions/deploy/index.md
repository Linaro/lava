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

The headers are sent both when the URL is checked during test job validation
and when the artifact is downloaded.

#### Authenticated downloads

Any authentication scheme that is carried by an HTTP header can be used to
download a private artifact, including `Bearer` tokens and HTTP Basic
authentication.

To keep the credentials out of the job definition, a header **value** can be
the name of one of your
[remote artifact tokens](../../job.md#secrets). LAVA replaces the name with
the token string when the job runs, so only the name is visible in the
definition, for example:

```yaml
- deploy:
    tmpfs:
      rootfs:
        url: https://example.com/private/rootfs.img.xz
        compression: xz
        headers:
          Authorization: remote-artifact-token-name
```

!!! warning "The whole value is replaced"
    The substitution matches the **complete** header value against the token
    names; it is not a string interpolation. Writing
    `Authorization: "Bearer bearer-token"` sends that string literally. The
    stored token must therefore be the full header value, for example:
    `Bearer 0123456789abcdef`.

For HTTP Basic authentication, store the pre-computed `Basic <base64>` value
for the remote artifact token value, where the base64 part is
`printf 'username:password' | base64`.

!!! note "base64 is not encryption"
    A Basic authentication header is a reversible encoding of the username
    and password. Storing it as a remote artifact token keeps it out of the
    job definition, but the token value is equivalent to the plain text
    password.

!!! info "Secrets cannot be used in URLs"
    The [`secrets`](../../job.md#secrets) block is only exported to the test
    shell; nothing substitutes it into a URL. Use `headers` to authenticate a
    download.

### URL

Specifies the URL to download.

URLs **must** use one of the supported protocols:

* `http://`
* `https://`
* `file://`
* `scp://`
* `downloads://`
* `rclone://`

URLs are checked during the test job validation to ensure that the file can be
downloaded. Missing files will cause the test job to end as `Incomplete`.

### File names

The file is named after the last part of the URL path. Some URLs have no name
there, for example a redirect endpoint, and then every image is saved as
`download` and they overwrite each other. Use `filename` to say what the file
should be called:

```yaml
      rootfs:
        url: https://example.com/download?id=42
        filename: rootfs.tar.xz
        compression: xz
```

Give the name of the file you download. LAVA drops the compression suffix
while it unpacks, the same as it does for a name taken from the URL, so the
example above ends up as `rootfs.tar`.

It must be a plain file name, without a directory part. It works for every
deploy method that downloads.

#### rclone

The `rclone://` protocol allows downloading artifacts from any storage backend
supported by [rclone](https://rclone.org/), including S3, Google Drive, Azure
Blob Storage, SFTP, and 70+ other providers.

The URL format is `rclone://remote-name/path/to/file` where `remote-name`
corresponds to a configured remote in the rclone configuration.

The rclone configuration can be provided in two ways via the job `secrets`
block. The dispatcher must have rclone installed.

**Option 1 — environment variables:**

```yaml
secrets:
  rclone_env:
    RCLONE_CONFIG_S3REMOTE_TYPE: "s3"
    RCLONE_CONFIG_S3REMOTE_PROVIDER: "AWS"
    RCLONE_CONFIG_S3REMOTE_ACCESS_KEY_ID: "AKIAIOSFODNN7EXAMPLE"
    RCLONE_CONFIG_S3REMOTE_SECRET_ACCESS_KEY: "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
    RCLONE_CONFIG_S3REMOTE_REGION: "us-east-1"

actions:
- deploy:
    to: tmpfs
    images:
      rootfs:
        url: rclone://s3remote/bucket/images/rootfs.img.gz
        compression: gz
```

The variable naming convention is `RCLONE_CONFIG_<REMOTE>_<OPTION>` where
`<REMOTE>` is the remote name in uppercase.

**Option 2 — inline config file:**

```yaml
secrets:
  rclone_config: |
    [s3remote]
    type = s3
    provider = AWS
    access_key_id = AKIAIOSFODNN7EXAMPLE
    secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
    region = us-east-1

actions:
- deploy:
    to: tmpfs
    images:
      rootfs:
        url: rclone://s3remote/bucket/images/rootfs.img.gz
        compression: gz
```

If both `rclone_env` and `rclone_config` are set, `rclone_env` takes priority.

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
* `overlay_backend`: which tool to use to modify `ext4` images: `auto`
  (the default), `e2fsprogs` or `guestfs`. With `auto`, LAVA uses `e2fsprogs`
  (`debugfs`) when it is available on the worker and falls back to
  `libguestfs`. Set this to override that choice, for example to force
  `guestfs` if an image does not work with the `e2fsprogs` backend.

`overlay_backend` can also be set directly under `deploy:` to apply to every
image in the deployment; a per-image value takes precedence over the
deploy-level one.

### LAVA overlay

In order to insert the LAVA overlay (that include the test definitions and
helpers), use `lava: true` as overlay.

```yaml
- deploy:
    to: usbg-ms
    image:
      url: https://raspi.debian.net/tested/20231109_raspi_4_bookworm.img.xz
      compression: xz
      format: ext4
      partition: 1
      overlays:
        lava: true
```

### Overlays

You can insert a tar archive or a file in the artifact. You should provide:

* `format`: the format of the overlay (`file` or `tar`).
* `path`: the path in the artifact
