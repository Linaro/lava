# Protocols

A protocol in LAVA is a method of interacting with external services using the
supported APIs instead of with direct shell commands. The protocol defines which
APIs are available, and the job pipeline determines when the API call is made.

Note that not all protocols can be called from all actions and not all protocols
are able to share data between actions.

## MultiNode

The MultiNode protocol allows multiple devices to work together as a group,
synchronizing operations and sharing data between them.

### API

The MultiNode API provides helper scripts that are available inside the test
shell on the DUT. The APIs can be used from the LAVA test shell definitions to
pass messages between devices in a group.

See [MultiNode job definition](../../user/advanced-tutorials/multinode.md#coordinating-via-apis)
for job example.

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

Data from the message is written to `/tmp/lava_multi_node_cache.txt` as
`key=value` pairs.

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

As with `lava-wait`, the message ID is persistent for the duration of the
MultiNode group, and the key-value pairs with the message will be stored in the
cache file.

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
