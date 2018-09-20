######################
# lava-dispatcher-base
######################
FROM debian:stretch-backports AS lava-dispatcher-base

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND noninteractive

# Depends
RUN apt-get update -q && \
    apt-get install --no-install-recommends --yes file python3-setuptools systemd-sysv tar && \
    apt-get install --no-install-recommends --yes python3-configobj python3-guestfs python3-jinja2 python3-magic python3-netifaces python3-nose python3-pexpect python3-pyudev python3-requests python3-setproctitle python3-tz python3-yaml python3-zmq

# Recommends
# Excluding: lxc, sudo
RUN apt-get install --no-install-recommends --yes bridge-utils debootstrap dfu-util git libguestfs-tools nfs-kernel-server ntp openbsd-inetd qemu-system-arm qemu-system-x86 rpcbind rsync ser2net telnet tftpd-hpa u-boot-tools unzip xz-utils

# Suggests
# Excluding: docker.io
RUN apt-get install --no-install-recommends --yes apache2 bzr img2simg simg2img

##################
# lava-server-base
##################
FROM lava-dispatcher-base AS lava-server-base

# Depends
RUN apt-get install --no-install-recommends --yes adduser apache2 gunicorn3 iproute2 libjs-excanvas libjs-jquery libjs-jquery-cookie libjs-jquery-flot libjs-jquery-typeahead libjs-jquery-ui libjs-jquery-watermark postgresql postgresql-client postgresql-common python3-setuptools systemd-sysv

# Recommends
RUN apt-get install --no-install-recommends --yes ntp openssh-client
