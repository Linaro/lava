# QDL

The `qdl` boot method allows to flash Qualcomm devices using the [qdl](https://github.com/linux-msm/qdl) tool.

```
- boot:
    method: qdl
    firehose_program: "prog_firehose_ddr.elf"
    rawprogram: "rawprogram*.xml"
    patch: "patch*.xml"
    path: "path-to-dir-inside-tarball"
    storage: "emmc"
    timeout:
      minutes: 5
```

## Installation

LAVA supports running `qdl` directly on the worker host or from a Docker container.
In both cases, LAVA administrators have to make sure `qdl` is installed on the worker.

The latest release is available at [https://github.com/linux-msm/qdl/releases](https://github.com/linux-msm/qdl/releases).

## Device configuration

## qdl parameters

Some of the `qdl` parameters must be provided in the job definition.

### firehose_program

Since each Qualcomm devices uses a different `firehose` protocol implementation,
the user must specify the filename of the `firehose` program to be used by `qdl`.
This filename is relative to the top tarball directory.
See [deploy-to-qdl](../deploy/to-qdl.md) for more details.

### rawprogram

List of `rawprogram` files to be used by `qdl`. The filenames should be delimited by whitespace
and should be specified relative to the root of the tarball defined in `qcomflash`.
See [deploy-to-qdl](../deploy/to-qdl.md) for more details.

### patch

List of `patch` files used by `qdl`. The filenames should be delimited by whitespace
and should be specified relative to the root of the tarball defined in `qcomflash`.
See [deploy-to-qdl](../deploy/to-qdl.md) for more details.

### storage

Storage device for `qdl` to write data to. Supported values include `emmc`, `ufs`, `spinor`, etc.
See [qdl documentation](https://github.com/linux-msm/qdl/blob/master/README.md) for more details.

### path

Path inside the downloaded tarball containing the `rawprogram` and `patch` files.
The paths referenced by `rawprogram` and `patch` files are relative, so `qdl` must be ran from this directory.
