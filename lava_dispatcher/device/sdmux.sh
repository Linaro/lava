#!/bin/bash
# based on  https://github.com/liyan/suspend-usb-device

#set -e

usage()
{
    cat<<EOF
This script will turn on/off power to a USB port. Its being
used in conjunction with the SD Mux device.

Power on/off a device or find its /dev/sdX with:
 $0 -d device_id on|off|deventry

Find the device ID from a /dev/entry with
$0 -f /dev/sdX

EOF
}

while getopts "f:d:" opt; do
	case $opt in
		f)  DEV=$OPTARG ;;
		d)  ID=$OPTARG ;;
		\?) usage ; exit 1 ;;
	esac
done

if [ -n "$DEV" ] ; then
	echo "Finding id for $DEV"
	DEVICE=$(udevadm info --query=path --name=${DEV} --attribute-walk | \
	egrep "looking at parent device" | head -1 | \
	sed -e "s/.*looking at parent device '\(\/devices\/.*\)\/.*\/host.*/\1/g")

	if [ -z $DEVICE ]; then
	    1>&2 echo "cannot find appropriate parent USB device, "
	    1>&2 echo "perhaps ${DEV} is not an USB device?"
	    exit 1
	fi

	# the trailing basename of ${DEVICE} is DEV_BUS_ID
	DEV_BUS_ID=${DEVICE##*/}
	echo Device: ${DEVICE}
	echo Bus ID: ${DEV_BUS_ID}

elif [ -n "$ID" ] ; then
	ACTION=${!OPTIND:-}
	DIR=/sys/bus/usb/devices/${ID}/${ID}*/host*/target*/*:0:0:0/block
	if [ $ACTION == "on" ] ; then
		if [ -d $DIR ] ; then
			echo "<sdmux script> already on" 1>&2
		else
			echo -n "${ID}" > /sys/bus/usb/drivers/usb/bind
			sleep 2
		fi
		device_path=`ls $DIR 2>/dev/null`
		if [ $? -ne 0 ] ; then
			echo "<sdmux script> No sdmux found at ${DIR}" 1>&2
			exit 1
		fi
		echo /dev/${device_path}

	elif [ $ACTION = "off" ] ; then
		echo "<sdmux script> Powering off sdmux: $ID"
		echo -n "${ID}" > /sys/bus/usb/drivers/usb/unbind
		echo -n '0' > /sys/bus/usb/devices/$ID/power/autosuspend_delay_ms
		echo -n 'auto' > /sys/bus/usb/devices/$ID/power/control
		sleep 2
	elif [ $ACTION = "deventry" ] ; then
		echo /dev/`ls $DIR`
	else
		echo "ERROR: Action must be on/off"
		usage; exit 1
	fi
else
	usage
fi
