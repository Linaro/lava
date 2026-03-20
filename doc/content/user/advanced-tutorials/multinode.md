# MultiNode job definition

A LAVA MultiNode job is a single LAVA job definition that runs multiple jobs
across multiple devices. It is implemented via the
[MultiNode](../../technical-references/job-definition/protocols.md#multinode)
protocol that allows the jobs to communicate via the protocol API and requests.

## How to avoid it

While the MultiNode support in LAVA is powerful and mature, it also introduces
significant complexity for writing and debugging the job definitions. We
recommend avoiding MultiNode unless it is truly required by your use case.

Since the introduction of the [docker test shell](./running-arbitrary-code-with-docker.md)
for single node jobs, MultiNode is no longer required in many scenarios.
Communicating with a DUT via a Docker container within a single node job is a
much simpler and more reliable approach. Give it a try before you start working
with the MultiNode.

## Dependency

[LAVA coordinator](../../technical-references/services/lava-coordinator.md)
service should be configured and reachable from all the workers involved in the
MultiNode jobs.

## Coordinating via APIs

The following example job uses the
[MultiNode APIs](../../technical-references/job-definition/protocols.md#api)
from the LAVA test shell to pass messages between the iPerf server and client for
starting the test.

```yaml hl_lines="71 72 125 128"
job_name: MultiNode iPerf test

visibility: public
priority: medium

timeouts:
  job:
    minutes: 30
  action:
    minutes: 5
  connection:
    minutes: 2
  actions:
    power-off:
      seconds: 30

# Define roles
protocols:
  lava-multinode:
    roles:
      server:
        device_type: ssh
        count: 1
      client:
        device_type: bcm2711-rpi-4-b
        count: 1
    timeout:
      minutes: 10

actions:
# Server actions
- deploy:
    role:
    - server
    to: ssh
    os: debian
    timeout:
      minutes: 5

- boot:
    role:
    - server
    method: ssh
    prompts:
    - 'root@x13:~#'
    timeout:
      minutes: 5

- test:
    role:
    - server
    protocols:
      lava-multinode:
      - action: multinode-test
        request: lava-wait
        messageID: start
        timeout:
          minutes: 10
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: iperf-server
        run:
          steps:
          - iperf -s &
          - echo $! > /tmp/iperf-server.pid
          - IP=$(ip route get 8.8.8.8 | grep -oP 'src \K\S+')
          - lava-test-case get-server-ip --shell echo "Server IP is ${IP}"
          - lava-send server-ready server_ip=${IP}
          - lava-wait client-done
          - kill -9 $(cat /tmp/iperf-server.pid)
      name: iperf-server
      path: inline/iperf-server.yaml
    timeout:
      minutes: 15

# Client actions
- deploy:
    role:
    - client
    to: usbg-ms
    image:
      url: http://198.18.0.1/tmp/images/rpi4/20231109_raspi_4_bookworm.img
      format: ext4
      partition: 1
      overlays:
        lava: true
    timeout:
      minutes: 5

- boot:
    role:
    - client
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@rpi4-20231108:'
    timeout:
      minutes: 5

- test:
    protocols:
      lava-multinode:
      - action: multinode-test
        request: lava-send
        messageID: start
        timeout:
          minutes: 10
    role:
    - client
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: iperf-client
        run:
          steps:
          - apt-get update -q
          - lava-test-case install-iperf --shell apt-get -q -y install iperf
          - lava-wait server-ready
          - SERVER_IP=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
          - lava-test-case iperf-to-server --shell iperf -c ${SERVER_IP} -t 10
          - lava-send client-done
      name: iperf-client
      path: inline/iperf-client.yaml
    timeout:
      minutes: 15
```

## Coordinating via requests

The following example job uses the
[MultiNode protocol requests](../../technical-references/job-definition/protocols.md#request)
across multiple job actions to configure the faster server waits for the slower
client.

```yaml hl_lines="36-42 109-116"
job_name: MultiNode iPerf test - wait for client

visibility: public
priority: medium

timeouts:
  job:
    minutes: 30
  action:
    minutes: 5
  connection:
    minutes: 2
  actions:
    power-off:
      seconds: 30

# Define roles
protocols:
  lava-multinode:
    roles:
      server:
        device_type: ssh
        count: 1
      client:
        device_type: bcm2711-rpi-4-b
        count: 1
    timeout:
      minutes: 10

actions:
# Server actions
- deploy:
    role:
    - server
    # Wait for the client.
    protocols:
      lava-multinode:
      - action: scp-overlay
        request: lava-wait
        messageID: start
        timeout:
          minutes: 10
    to: ssh
    os: debian
    timeout:
      minutes: 5

- boot:
    role:
    - server
    method: ssh
    prompts:
    - 'root@x13:~#'
    timeout:
      minutes: 5

- test:
    role:
    - server
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: iperf-server
        run:
          steps:
          - iperf -s &
          - echo $! > /tmp/iperf-server.pid
          - IP=$(ip route get 8.8.8.8 | grep -oP 'src \K\S+')
          - lava-test-case get-server-ip --shell echo "Server IP is ${IP}"
          - lava-send server-ready server_ip=${IP}
          - lava-wait client-done
          - kill -9 $(cat /tmp/iperf-server.pid)
      name: iperf-server
      path: inline/iperf-server.yaml
    timeout:
      minutes: 15

# Client actions
- deploy:
    role:
    - client
    to: usbg-ms
    image:
      url: http://198.18.0.1/tmp/images/rpi4/20231109_raspi_4_bookworm.img
      format: ext4
      partition: 1
      overlays:
        lava: true
    timeout:
      minutes: 5

- boot:
    role:
    - client
    method: minimal
    auto_login:
      login_prompt: 'login:'
      username: root
    prompts:
    - 'root@rpi4-20231108:'
    timeout:
      minutes: 5

- test:
    role:
    - client
    protocols:
      lava-multinode:
      - action: multinode-test
        # Notify sever to start.
        request: lava-send
        messageID: start
        timeout:
          minutes: 10
    definitions:
    - from: inline
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: iperf-client
        run:
          steps:
          - apt-get update -q
          - lava-test-case install-iperf --shell apt-get -q -y install iperf
          - lava-wait server-ready
          - SERVER_IP=$(cat /tmp/lava_multi_node_cache.txt | cut -d = -f 2)
          - lava-test-case iperf-to-server --shell iperf -c ${SERVER_IP} -t 10
          - lava-send client-done
      name: iperf-client
      path: inline/iperf-client.yaml
    timeout:
      minutes: 15
```
