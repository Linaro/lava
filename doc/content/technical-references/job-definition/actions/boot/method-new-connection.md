# New Connection

The `new_connection` boot method can be used to switch to a new connection.
If the kernel and the device are both appropriately configured, a test can use
a new connection to isolate test and kernel messages.

If the second [connection](../../../configuration/device-dictionary.md#connections)
`uart0` is configured in the device dictionary, the connection can be created in
a separate namespace.

```yaml
- boot:
    namespace: isolation
    connection: uart0
    method: new_connection
```

The `new_connection` boot method **must** use a different namespace to all other
actions in the test job. The test actions **must** pass this namespace label as
the `connection-namespace`.

```yaml
- test:
    namespace: hikey-oe
    connection-namespace: isolation
    definitions:
    - from: git
      repository: https://gitlab.com/lava/functional-tests.git
      path: posix/smoke-tests-basic.yaml
      name: smoke-tests
    timeout:
      minutes: 5
```

## Example device

```jinja title="Connection snippet"
{% extends 'n1sdp.jinja2' %}

{% set connection_list = ['uart0', 'uart1', 'uart2', 'uart3'] %}
{% set connection_commands = {
  'uart0': 'telnet w1 7007',
  'uart1': 'telnet w1 7008',
  'uart2': 'telnet w1 7009',
  'uart3': 'telnet w1 7010'
} %}
{% set connection_tags = {
  'uart0': ['primary', 'telnet'],
  'uart1': ['telnet'],
  'uart2': ['telnet'],
  'uart3': ['telnet']
} %}
```

## Example job

```yaml
job_name: new_connection job
device_type: n1sdp

priority: medium
visibility: public

timeouts:
  job:
    minutes: 15
  connection:
    minutes: 5

actions:
- deploy:
    namespace: default
    to: flasher
    images:
      recovery_image:
        url: https://storage.lavacloud.io/health-checks/n1sdp/board-firmware.zip
        compression: zip
    timeout:
      minutes: 5

- boot:
    namespace: default
    method: minimal
    timeout:
      minutes: 5

- boot:
    namespace: uart_one
    method: new_connection
    connection: uart1
    timeout:
      minutes: 5

- test:
    namespace: uart_one
    connection-namespace: uart_one
    interactive:
    - name: int_1
      prompts: ["Press ESCAPE for boot options"]
      script:
      - command:
    timeout:
      minutes: 10
```
