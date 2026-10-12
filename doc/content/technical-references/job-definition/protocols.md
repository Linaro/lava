# Protocols

A protocol in LAVA is a method of interacting with external services using the
supported APIs instead of with direct shell commands. The protocol defines which
APIs are available, and the job pipeline determines when the API call is made.

Note that not all protocols can be called from all actions and not all protocols
are able to share data between actions.

## MultiNode

The MultiNode protocol allows multiple devices to work together as a group,
synchronizing operations and sharing data between them.

```yaml
protocols:
  lava-multinode:
    roles:
      server:
        device_type: qemu
        count: 1
        essential: true
      client:
        device_type: bcm2711-rpi-4-b
        count: 2
        tags:
        - usb-hub
    timeout:
      minutes: 10

actions:
- deploy:
    role:
    - server
    - client
    ...
```

The job is split into one sub job per device. Each sub job only runs the
actions listing its role.

!!! note
    In a MultiNode job:

    * every action must have a `role` list
    * `device_type`, `context`, `environment` and `tags` are not allowed at the
      top level of the job definition. They are defined for each role.

### roles

Required. A dictionary of roles. The key is the name of the role.

| Key | Description |
| --- | ----------- |
| `device_type` | Required. The device type to use for this role |
| `count` | Required. The number of devices for this role. Can be `0` |
| `device` | Optional. Use this specific device. Requires `count: 1` |
| `worker` | Optional. Only use devices attached to this worker |
| `tags` | Optional. The [device tags](./job.md#tags) required for this role |
| `context` | Optional. The [job context](../../introduction/glossary.md#job-context) for this role |
| `environment` | Optional. The [environment](./environment.md#multinode) for this role |
| `essential` | Optional. See [essential](#essential) |
| `timeout` | Optional. The default timeout of the API calls for this role. Overridden by the group [timeout](#timeout) |

#### essential

When a sub job of an essential role is canceled or finishes as `Incomplete`,
LAVA cancels all the other sub jobs of the group.

Use it for the roles the other roles depend on, for instance a server: if the
server fails, the clients can't succeed and would only wait for their
timeouts.

```yaml
protocols:
  lava-multinode:
    roles:
      server:
        device_type: qemu
        count: 1
        essential: true
```

### Connection roles

A role can be a connection to the device of another role instead of a device.
For instance, a `guest` role can connect over SSH to a virtual machine started
by the `host` role.

```yaml
protocols:
  lava-multinode:
    roles:
      host:
        device_type: qemu
        count: 1
      guest:
        connection: ssh
        count: 2
        host_role: host
        expect_role: host
        request: lava-start
        timeout:
          minutes: 10
```

| Key | Description |
| --- | ----------- |
| `connection` | Required. The connection type, for instance `ssh` |
| `count` | Required. The number of connections |
| `host_role` | Required. The role of the device to connect to. This role must have `count: 1` |
| `expect_role` | Required. The role allowed to start the connection jobs |
| `request` | Optional. `lava-start` to delay the start of the connection jobs |
| `timeout` | Optional. How long to wait for `lava-start`. Defaults to 90 seconds |
| `essential`, `tags`, `context` | Optional. As for [roles](#roles) |

A connection role can't use `device_type`, `device` or `worker`.

`host_role` is used by the scheduler: the connection jobs run on the worker of
the `host_role` device.

#### lava-start

With `request: lava-start`, the connection jobs do not start immediately: they
wait until every device of the `expect_role` sends the `lava_start` message.
This allows the host to prepare the services needed by the connection jobs, like
booting a virtual machine, before they start.

The host sends the message when it is ready, from a test definition:

```yaml
- test:
    role:
    - host
    definitions:
    - from: inline
      name: lava-start
      path: inline/lava-start.yaml
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: lava-start
        run:
          steps:
          - lava-send lava_start
```

`expect_role` can't be the role declaring `lava-start`.

!!! note
    When the group also defines a [timeout](#timeout), the group timeout is
    used instead of the role `timeout`.

### timeout

Optional. The default timeout of the [MultiNode API](#api) calls. Defaults to
30 seconds.

```yaml
protocols:
  lava-multinode:
    roles:
      ...
    timeout:
      minutes: 10
```

### pool_pattern

`string` (1–200 characters)

A glob pattern (as understood by [fnmatch](https://docs.python.org/3/library/fnmatch.html))
used to keep every device of the group inside the same *pool*. A pool is
described by a device tag: when `pool_pattern` is set, the scheduler will only
use devices that have at least one tag matching the pattern, and every device
of the group will share the same matching tag.

```yaml
protocols:
  lava-multinode:
    pool_pattern: "lab-*"
    roles:
      server:
        device_type: qemu
        count: 1
      client:
        device_type: bcm2711-rpi-4-b
        count: 1
```

With the definition above, and devices tagged `lab-paris` or `lab-lyon`, the
group will either run entirely on `lab-paris` devices or entirely on
`lab-lyon` devices, but never on a mix of both.

This is useful when the devices of a group have to be physically connected
together, for instance when they share a network switch, a power supply or a
USB hub.

!!! note
    The pattern has to match the **whole** tag name, `lab-` would not match the
    `lab-paris` tag while `lab-*` would. The supported wildcards are `*` (any
    number of characters), `?` (a single character) and `[seq]` (any character
    in *seq*).

!!! note
    `pool_pattern` is only meaningful for MultiNode jobs.

The pool is unrelated to the [tags](./job.md#tags) requested by a role: a role
can request tags *and* the job can define a `pool_pattern`. In that case the
device has to satisfy both.

!!! warning
    The devices of a group are reserved one by one. Once the first device of
    the group has been reserved, the pool is fixed and the remaining sub jobs
    will wait for devices of that pool only. If the pool never has enough idle
    devices, the job stays queued until the
    [queue timeout](./timeouts.md) expires.

### API

The MultiNode API provides helper scripts that are available inside the test
shell on the DUT. The APIs can be used from the LAVA test shell definitions to
pass messages between devices in a group.

See [MultiNode job definition](../../user/advanced-tutorials/multinode.md#coordinating-via-apis)
for job example.

The API uses the connection already available to LAVA. It is meant for short
messages, not for transferring files or large amounts of data. Test definitions
which need to transfer files have to set up their own network access and
transfer method.

!!! tip "Debugging"
    Avoid running complex commands inside the API calls. Prepare and print the
    data in a separate step before sending it, so that the values appear in the
    test job logs.

    Do not wrap the API calls with `lava-test-case`: errors in the API call
    would be hidden and each call would create a duplicate test case.

#### lava-group

Print one line per device in the group:

```shell
lava-group
```

Output format: `<job_id>\t<role>`:

```plain
12345     client
12346     loadbalancer
12347     backend
12348     backend
```

Print job IDs for devices with the specified role, one per line:

```shell
lava-group <role>
```

Example output:

```plain
$ lava-group client
12345
$ lava-group backend
12347
12348
```

Exit with non-zero if the role doesn't exist:

```shell
$ lava-group server ; echo $?
1
```

#### lava-role

Print the role of the current device:

```shell
lava-role
```

Example output:

```plain
server
```

Print all roles in the MultiNode group, one role per line:

```shell
lava-role list
```

Example output:

```plain
server
client
```

#### lava-self

Report the job ID of the current device:

```shell
lava-self
```

#### lava-send

Sends a message to the group with optional key-value data. This is
non-blocking — the message is guaranteed to be available to all members, but
some may never retrieve it.

The message ID is persistent for the lifetime of the group. Re-sending a
different message with the same ID is not supported.

```shell
lava-send <message-id> [key1=val1 [key2=val2] ...]
```

!!! warning
    In the whitespace-separated `key=value` pairs, the key name must match the
    `\w+` pattern. This means only letters (`a–z, A–Z`), digits (`0–9`), and
    underscore (`_`) are allowed in the key name. In the values, quoted
    white spaces are allowed.

#### lava-sync

Global synchronization primitive. Sends a message, and waits for the same
message from all the other devices.

```shell
lava-sync <message>
```

!!! note
    All devices in the group must call `lava-sync` with the same message,
    otherwise it will block until timeout. `lava-sync foo` is effectively the
    same as `lava-send foo` followed by `lava-wait-all foo`.

#### lava-wait

Blocks until any device in the group sends a message with the given ID.

```shell
lava-wait <message-id>
```

The data from the message is written to the [cache file](#cache-file).

!!! note
    The message ID data is persistent for the life of the MultiNode group. The
    data can be retrieved at any later stage using `lava-wait` and as the data
    is already available, there will be no waiting time for repeat calls. If
    devices continue to send data with the associated message ID, that new data
    will continue to be added to the stored data for that message ID and will be
    returned by subsequent calls to `lava-wait` for that message ID. Use
    different message ID(s) if you don’t want this effect.

#### lava-wait-all

`lava-wait-all` operates in different ways, depending on the presence of the
role parameter.

Waits until **all** devices in the group send a message with the given ID.
Every device must use `lava-send` with the same ID, or this call will block
until the timeout.

```shell
lava-wait-all <message-id>
```

Wait until all devices with the specified role send the message:

```shell
lava-wait-all <message-id> <role>
```

With a role, the devices of that role do **not** wait: they send the message
and continue. Make sure that these devices keep running long enough for the
waiting devices to receive the message and act on it, typically with a
`lava-sync` once the waiting devices have completed their task.

As with `lava-wait`, the message ID is persistent for the duration of the
MultiNode group, and the key-value pairs with the message will be stored in the
[cache file](#cache-file).

!!! note
    `lava-sync` and `lava-wait-all` make all the devices of the group run at the
    speed of the slowest one, up to the point where the call is made.

#### Cache file

`lava-wait` and `lava-wait-all` write the data received with the message to
`/tmp/lava_multi_node_cache.txt` on the DUT. The file is replaced on each call.

Each line contains the job ID of the sender, a colon and one `key=value` pair:

```plain
12345:ipaddr=192.168.0.3
12346:ipaddr=192.168.0.4
```

For example, to retrieve the value sent by the server:

```shell
lava-wait server-ready
SERVER_IP=$(grep ":ipaddr=" /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
```

### Request

This protocol allows actions within the pipeline to make requests using the
MultiNode API outside a test definition by wrapping the call inside the protocol.
This allows synchronization to happen during deploy or boot, not just within test
shells.

Actions check for protocol calls at the start of the run step. Only the named
action instance inside the pipeline will make the call. The use of the protocol
requests is an advanced use of LAVA and relies on the test job writer carefully
planning how the job will work.

See [MultiNode job definition](../../user/advanced-tutorials/multinode.md#coordinating-via-requests)
for job example.

#### lava-send

Send a message with optional key-value message to the group:

```yaml
protocols:
  lava-multinode:
  - action: prepare-scp-overlay
    request: lava-send
    messageID: ipv4
    message:
      ipaddr: '<value>'
    timeout:
      minutes: 5
```

#### lava-sync

Synchronize all devices in the group at a specific point in the pipeline:

```yaml
protocols:
  lava-multinode:
  - action: prepare-scp-overlay
    request: lava-sync
    messageID: start
    timeout:
      minutes: 5
```

#### lava-wait

Waits for any device in the group to send a message with the given ID. To
update the value available to the action, ensure the key exists in the matching
`lava-send` and prefix the value with `$` in the job submission:

```yaml
protocols:
  lava-multinode:
  - action: prepare-scp-overlay
    request: lava-wait
    messageID: ipv4
    message:
      ipaddr: $ipaddr
    timeout:
      minutes: 5
```

This makes the received data available to the action:

```yaml
{'message': {'ipaddr': '192.168.0.3'}, 'messageID': 'ipv4'}
```

#### lava-wait-all

Wait for all devices to send a message:

```yaml
protocols:
  lava-multinode:
  - action: prepare-scp-overlay
    request: lava-wait-all
    messageID: ipv4
    message:
      ipaddr: $ipaddr
    timeout:
      minutes: 5
```

Wait for all devices with a specific role to send a message:

```yaml
protocols:
  lava-multinode:
  - action: prepare-scp-overlay
    request: lava-wait-all
    role: server
    messageID: ipv4
    message:
        ipaddr: $ipaddr
    timeout:
      minutes: 5
```

## XNBD

The `lava-xnbd` protocol allocates the port used by the NBD server of an
[NBD deployment](./actions/deploy/to-nbd.md). The NBD server is stopped at the
end of the job.

The protocol is declared at the top level of the job definition:

```yaml
protocols:
  lava-xnbd:
    port: auto
```

* `port`: required. Either `auto` or a fixed port number. With `auto`, LAVA
  uses the `nbd_server_port` from the [dispatcher configuration](../configuration/dispatcher.md)
  if it is a number, or a free port between 55000 and 56000.
* `timeout`: optional.

The `nbd-deploy` action requests the port with `set_port`:

```yaml
- deploy:
    to: nbd
    protocols:
      lava-xnbd:
      - action: nbd-deploy
        request: set_port
    ...
```
