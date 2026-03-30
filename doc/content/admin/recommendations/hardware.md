# Hardware

LAVA supports both `amd64` and `arm64` architectures. It uses a
[server–worker](../../technical-references/architecture.md) model. The server
and worker hardware requirements described here are guidelines, not hard
limits. You can start with the recommendations, measure real load, and add
capacity when needed.

## LAVA server

A small LAVA instance can be deployed on fairly modest hardware.

We recommend a minimum of 4GB of RAM to cover the runtime needs of the database
server, the application server, and the web server. 8 GB RAM is preferred, as
PostgreSQL alone may consume 1–2 GB on a busy instance.

For storage, reserve about 80GB for job data to avoid frequent cleanup of
job logs. Keep in mind that storage requirements will grow over time. Unless
storage is unlimited, a job log retention or cleanup policy is necessary. SSDs
are strongly preferred, as spinning disk is a common performance bottleneck.

If you are deploying many devices and expect to be running large numbers of
concurrent jobs, you will obviously need more RAM and disk space.

## LAVA worker

### Classic LAVA worker

A LAVA worker can run on fairly modest hardware. Exact requirements depend on
the number of attached tests devices and concurrent jobs the worker is expected
to handle.

When a standard PC is used as a worker, several additional pieces of equipment
are needed to support test automation:

- PDU (Power Distribution Unit) for power-cycling DUTs remotely (e.g., APC PDU)
- USB serial adapters for serial console access to each DUT (e.g., FTDI-based adapters)
- Powered USB hub for switching DUT USB ports
- Ethernet switch for providing isolated network environment

Sourcing reliable, compatible equipment and debugging hardware-level issues
(e.g., flaky USB, power glitches, serial dropouts) can be surprisingly
time-consuming. An integrated solution like the [**LAA**](#linaro-automation-appliance)
is designed and well tested to eliminate most of that effort.

### Linaro Automation Appliance

The [**Linaro Automation Appliance (LAA)**](https://docs.lavacloud.io/) is a
fully integrated device testing solution. It provides everything needed by most
hardware automation tasks while also allowing to share DUTs with remote users
and customers.

The LAA integrates power control, USB switching, USB OTG (mass storage gadget),
serial console, and secure network connectivity into a single managed unit. This
solution significantly reduces per-device wiring complexity and avoids the
reliability issues commonly associated with assembling untested generic hubs
and PDUs.

The LAA is the recommended worker for efficient LAVA deployments. It significantly
accelerates test device enablement in LAVA while ensuring more repeatable and
reliable test results.

For more details, please refer to [LAA documentation][LAA].

## See also

- [LAVA architecture](../../technical-references/architecture.md)
- [LAVA deployment topology](./topology.md)
- [LAVA installation](../basic-tutorials/instance/install.md)
- [LAVA Docker worker](../advanced-tutorials/docker-worker.md)
- [Raspberry Pi4B as a LAVA worker](../advanced-tutorials/deploying-rpi4b-as-worker.md)

--8<-- "refs.txt"
