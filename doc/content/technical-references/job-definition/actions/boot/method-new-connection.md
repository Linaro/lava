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
