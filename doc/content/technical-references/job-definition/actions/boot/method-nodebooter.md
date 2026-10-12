# Nodebooter

The `nodebooter` boot method netboots the DUT using a nodebooter container
running on the LAVA worker. The container provides the DHCP and TFTP services
used by the DUT and by its network cards (NICs) to boot.

```yaml
- deploy:
    to: downloads
    images:
      boot:
        url: https://example.com/boot.img
      nic0:
        url: https://example.com/nic0.img

- boot:
    method: nodebooter
    docker:
      image: nodebooter:latest
      local: true
    prompts:
    - 'root@dut:~#'
```

LAVA:

1. starts the nodebooter container (privileged, on the host network)
2. restarts the `setup_networks`, `naas` and `nodebooter` services in the
   container
3. registers the DUT, and its NICs, using the nodebooter API, with the
   downloaded images as boot files
4. resets the DUT

When the job ends, LAVA stops the container and removes the files created by
nodebooter for this DUT.

## Images

The images are downloaded by a previous deploy action:

* `boot`: required. The boot file of the DUT.
* `nic0` to `nic3`: optional. The boot file of each NIC.

## docker

Required. The nodebooter docker image to use:

* `image`: required. The name of the image.
* `local`: optional. Use a local image instead of pulling it.
* `login`: optional. The `registry`, `user` and `password` used to pull the
  image.

## auto_login

See [auto_login](common.md#auto_login).

## prompts

See [prompts](common.md#prompts).

## transfer_overlay

See [transfer_overlay](common.md#transfer_overlay).

## Device configuration

The device-type template must define the `nodebooter` boot method. With
`base-grub.jinja2`, set `has_nodebooter` in the device dictionary:

```jinja
{% set has_nodebooter = true %}
```

The DUT network configuration is set in the
[environment](../../../configuration/device-dictionary.md#environment) of the
device dictionary:

| Variable | Description |
| -------- | ----------- |
| `DUT_MAC` | Required. MAC address of the DUT |
| `DUT_IFACE` | Required. Network interface of the worker connected to the DUT |
| `NIC0_MAC` to `NIC3_MAC` | MAC address of each NIC, required when the matching `nic` image is used |

```jinja
{% set environment = {
  'DUT_MAC': '00:11:22:33:44:55',
  'DUT_IFACE': 'eth1',
  'NIC0_MAC': '00:11:22:33:44:66'} %}
```

The nodebooter data is stored on the worker in `/data/nodebooter/`.
