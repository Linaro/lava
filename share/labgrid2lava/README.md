# labgrid2lava

Convert labgrid environment config to lava device and job definitions.

## Installation

On Debian-based distributions:

```bash
sudo apt install python3-dacite python3-jinja2 python3-yaml
```

Using a Python virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install dacite jinja2 PyYAML
```

## Usage example

### Convert

Docker:

```bash
python3 ./converter.py -l examples/docker.yaml -o output/ -d docker

```

RPi3 uboot:

```bash
python3 ./converter.py -l examples/uboot.yaml -o output/ -d bcm2837-rpi-3-b-32
```

LAVA `device.yaml` and `job.yaml` definitions are saved to the `output` directory.

### Run

Original labgrid run command:

```bash
pytest --lg-env examples/docker.yaml test_shell.py
```

Equivalent lava run command:

```bash
lava-run --job-id 1 \
  --output-dir ./1 \
  --device ./output/device.yaml \
  ./output/job.yaml
```

Using the dev version lava-run from this repo:

```bash
PYTHONPATH=../../ python3 ../../lava/dispatcher/lava-run \
  --job-id 1 \
  --output-dir ./1 \
  --device ./output/device.yaml \
  ./output/job.yaml
```

LAVA job pipeline description, logs and result are saved to the specified output
directory.

## Supported Features

Refer to the `LgConfig`, `Resources` and `Drivers` in the `converter.py` for
supported labgrid modules.

When converting a labgrid env config, un-supported modules will be listed. If needed,
the converter can be extended. Here are the steps:

* In the `converter.py`, define a dataclass for each module.
* Update the lava device and job templates to define the equivalent blocks for rendering.
* Rerun the convert command.
