FROM debian:stretch-backports

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update -q

RUN apt-get install --no-install-recommends --yes file python3-setuptools systemd-sysv tar
RUN apt-get install --no-install-recommends --yes python3-configobj python3-guestfs python3-jinja2 python3-magic python3-netifaces python3-nose python3-pexpect python3-pyudev python3-setproctitle python3-tz python3-yaml python3-zmq
RUN apt-get install --no-install-recommends --yes -t stretch-backports python3-requests
RUN apt-get install --no-install-recommends --yes bridge-utils debootstrap dfu-util git libguestfs-tools nfs-kernel-server ntp openbsd-inetd qemu-system-arm qemu-system-x86 rpcbind rsync ser2net telnet tftpd-hpa u-boot-tools unzip xz-utils
RUN apt-get install --no-install-recommends --yes apache2 bzr img2simg simg2img
