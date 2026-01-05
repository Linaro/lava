# Core Features

## Automated validation

LAVA is designed for automated workflows to create, submit, and process test
jobs to validate the development process.

## Distributed architecture

LAVA uses a distributed architecture built around a central LAVA server and
multiple LAVA workers.

LAVA workers can be deployed behind firewalls, allowing organizations to
integrate internal test infrastructure while preserving network isolation and
security. Labs that host LAVA workers and DUTs can be deployed remotely as
remote labs.

This design enables horizontal scaling and flexible deployment across
geographically distributed and network-restricted environments.

## Privacy support

LAVA test jobs or device types can be kept private to selected groups,
individuals or teams. Entire LAVA instance can also be configured as private.
A private instance requires authentication for all access.

## Parallel scheduling

Multiple test jobs run at the same time across multiple devices.

## MultiNode test jobs

LAVA test jobs can be run as a single group of tests involving multiple devices.

## Containerized testing control

Test jobs can run arbitrary code in isolated containers on the worker to control
test devices. The feature enables single node jobs for scenarios that used to
require complex MultiNode test jobs.

## Hardware sharing

Uncommon hardware is shared between disparate groups to maximize usage. Remote
access via hacking sessions allows developers to interactively debug on physical
devices.

## Wide device coverage

A large number of device types can be supported, with instances ranging from one
to more than a hundred devices available for test jobs.

## Multi-platform support

Test jobs can be run on systems running various UNIX flavors, Android, or IoT
platforms like Zephyr. LAVA supports a wide range of deploy, boot, and test
methods to accommodate testing with different platforms.

## Complex network testing

LAVA supports testing scenarios that require reconfigurable networking across
multiple devices, including VLAN configuration and multiple network interfaces.

## Live result reporting

If a test job fails, all results up to the point of failure are retained.

## Result Queries and charts

LAVA result queries allow user to track test results over time. LAVA result
charts can visualize trends in test pass rates, performance measurements, and
other metrics.

## Flexible notifications

LAVA job completion can trigger notifications via email, IRC, or webhook
callbacks.

## Data export for customization

LAVA provides APIs for exporting test job data to support custom frontends and
dashboards tailored to specific needs.

## REST API

LAVA provides REST APIs alongside the `lavacli` client, enabling seamless
integration with CI systems and supporting LAVA instance management through
Infrastructure as Code (IaC).

--8<-- "refs.txt"
