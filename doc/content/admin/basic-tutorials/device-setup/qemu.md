# QEMU device setup

LAVA can use qemu as a DUT and run test inside QEMU.

## Create device-type

[Create the device type](common.md#create-device-type) using the name **`qemu`**.

## Create device

1. [Add the device](common.md#add-device) using the following settings:
    * **Device Type:** `qemu`
    * **Hostname:** A unique name (e.g., `qemu-01`)
2. [Add the device configuration](common.md#add-device-configuration).

    For a simple qemu job, this device dictionary would work:

    ```jinja
    {% extends "qemu.jinja2" %}

    {% set netdevice = "user" %}
    {% set memory = 1024 %}
    ```

    !!! tip
        If `/dev/kvm` is unavailable on the worker, add `{% set no_kvm = True %}` to
        the dictionary.

## Submit a job

Submit this simple test job:

```yaml
--8<-- "jobs/qemu.yaml"
```

The job page will look like [this](https://validation.linaro.org/scheduler/job/2009038).

## Configure bridged network

For `qemu-nfs` and `qemu-iso` boot methods, `netdevice` must be set to `tap`
in either the job context or the device dictionary. The tap interface must be
linked to a bridged interface that provides access to the worker and maybe also
the Internet.

If the network bridge is not configured yet, follow the steps below to create
one.

!!! note
    These instructions are only validated on Debian. You may need to adjust
    them for other distributions.

1. Install required packages:

    ```bash
    sudo apt install iproute2 dnsmasq
    ```

2. Create the bridge:

    ```bash
    sudo ip link add name br-lava type bridge
    sudo ip addr add 192.168.66.1/24 dev br-lava
    sudo ip link set br-lava up
    ```

3. Make the bridge persistent:

    ```bash
    sudo mkdir -p /etc/network/interfaces.d
    sudo tee /etc/network/interfaces.d/br-lava > /dev/null <<'EOF'
    auto br-lava
    iface br-lava inet static
        address 192.168.66.1
        netmask 255.255.255.0
        bridge_ports none
        bridge_stp off
    EOF
    ```

4. Enable DHCP for the bridge:

    ```bash
    sudo tee /etc/dnsmasq.d/br-lava.conf > /dev/null << 'EOF'
    interface=br-lava
    bind-interfaces
    dhcp-range=192.168.66.2,192.168.66.100,12h
    dhcp-option=option:router,192.168.66.1
    dhcp-option=option:dns-server,8.8.8.8
    except-interface=lo
    port=0
    EOF
    sudo systemctl restart dnsmasq
    ```

5. Configure QEMU to use the bridge:

    ```bash
    sudo cp /etc/qemu-ifup /etc/qemu-ifup.original
    sudo tee /etc/qemu-ifup > /dev/null << 'EOF'
    #!/bin/sh -ex

    TAP="$1"
    BRIDGE=br-lava

    ip link set "$TAP" up
    ip link set "$TAP" master "$BRIDGE"
    EOF
    ```

6. Optionally, allow the `br-lava` interface to access the Internet.

    Add NAT masquerading rules:

    ```shell
    sudo iptables -t nat -A POSTROUTING -o <eth0> -j MASQUERADE
    sudo iptables -A FORWARD -i br-lava -o <eth0> -j ACCEPT
    sudo iptables -A FORWARD -i <eth0> -o br-lava -m state --state RELATED,ESTABLISHED -j ACCEPT
    ```

    !!! note
        Replace `<eth0>` with the name of the interface that provides Internet access.

    Make rules persistent:

    ```shell
    sudo apt-get install -y iptables-persistent
    sudo netfilter-persistent save
    ```

--8<-- "refs.txt"
