.. index:: device integration - IoT

.. _integrating_iot:

Internet of Things
******************

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

This was the first CMSIS device, USB mass storage flashing needs no extra tools
installed on the dispatcher.

The board resets after being flashed, the usb mount and serial device go away
and return. LAVA can use the serial device udev add action to know its safe to
connect to serial. Connecting to the serial port also causes the app to
restart, but cannot do that before flash is complete or the image can be
corrupted.

Cons
----

The serial device goes away when the board resets after flashing, so LAVA can
only try and reconnect to serial as soon as udev sees it return. This means
that LAVA can miss the first line of output due to this race condition. This
race condition is a problem for all CMSIS devices.

After the integration was complete, this device was moved to use PyOCD to reset
the app without the serial connection dropping.
