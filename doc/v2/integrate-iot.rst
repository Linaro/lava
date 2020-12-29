.. index:: device integration - IoT

.. _integrating_iot:

Internet of Things (IoT) Boards
*******************************

These are quick notes on using MCU/IoT level boards with LAVA.

.. important:: Make sure you have read :ref:`adding_new_device_types` first.

Arduino101
==========

A separate serial connection means board can be reset without serial
interruption, very good, saves all the timing issues of trying to reconnect to
the serial line before the app starts.

The DFU utility has option to reset the board after flashing, so no need to use
power control for that bit.

Working upstream zephyr binaries were available to support integration.

Cons
----

The device draws power from both the 5v header and the USB flashing port, so
you need power control for USB and not use the 5v connector. Not a problem for
the lab hubs but I had to make a usb power control solution for home.

FRDM-K64F
=========

This was among the first CMSIS-DAP devices added to LAVA, and known to be
generally well supported and stable. USB mass storage flashing needs no extra
tools installed on the dispatcher.

Depending on the DAP firmware settings, the board resets after being flashed,
or not. The USB mount and serial device go away and return. LAVA can use the
serial device udev add action to know its safe to
connect to serial. Connecting to the serial port also causes the app to
restart, but cannot do that before flash is complete or the image can be
corrupted.

While flashing via USB mass storage device is conceptually easy deployment
method, experience across different kinds of host hardware showed that there
may be variations in behavior and compatibility issues. Oftentimes, they can
be worked around by a delay after flashing process, before proceeding to
serial connection, etc. This delay can be controlled via the following setting
in a device dictionary (for particular device)::

    {% block cmsis_dap_params %}
    # cmsis-dap boot method params in YAML syntax
    post_unmount_delay: 3
    {% endblock cmsis_dap_params %}

Note that 3s is already applied safe default for this setting.

Cons
----

The serial device goes away when the board resets after flashing, so LAVA can
only try and reconnect to serial as soon as udev sees it return. This means
that LAVA can miss the first line of output due to this race condition. This
race condition is a problem for all CMSIS devices.

After the integration was complete, this device was moved to use PyOCD to reset
the app without the serial connection dropping.
