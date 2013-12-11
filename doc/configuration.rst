.. _dispatcher_configuration:

Configuration files for lava-dispatcher
=======================================

lava-dispatcher looks for files in:

 * Alongside the installation/source tree for the default values
   (i.e. this directory).

 * /srv/lava/<instance>/etc/lava-dispatcher

Each config directory can contain two files and two directories:

 * lava-dispatcher.conf

   This file defines global settings of the dispatcher.  You will
   almost certainly need to customize LAVA_SERVER_IP and LAVA_PROXY
   for your install. LAVA_PROXY could be empty if no proxy server
   available.

 * device-defaults.conf

   This file defines default values for all devices.  You probably
   won't need to customize it.

 * device-types/

   This directory contains a config file for each :term:`device type`. You
   probably won't need to customize the settings for device types that
   are already supported by lava-dispatcher, but if you are working on
   supporting a new class of device, you will need to add a file here.

 * devices/

   This directory contains a file per :term:`DUT` that can be targeted by
   lava-dispatcher.  For the most part this file just needs to contain
   a line "device_type = <device type>", although other settings can
   be included here.  You will definitely need to tell lava-dispatcher
   about the devices you have!
