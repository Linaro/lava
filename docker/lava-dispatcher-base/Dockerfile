FROM debian:bullseye-slim

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND noninteractive

RUN echo 'deb http://deb.debian.org/debian bullseye-backports main' > /etc/apt/sources.list.d/backports.list && \
    mkdir -p /usr/share/man/man1 /usr/share/man/man7 && \
    apt-get update -q && \
    apt-get install --no-install-recommends --yes python3-voluptuous python3-yaml && \
    apt-get install --no-install-recommends --yes bmap-tools python3-aiohttp python3-configobj python3-guestfs python3-jinja2 python3-magic python3-netifaces python3-pexpect python3-pyudev python3-requests python3-setproctitle python3-tz python3-yaml && \
    apt-get install --no-install-recommends --yes android-sdk-libsparse-utils docker.io dfu-util git libguestfs-tools ser2net telnet tftpd-hpa u-boot-tools unzip xz-utils zstd rpcbind nfs-common && \
    apt-get install --no-install-recommends --yes -t bullseye-backports qemu-system-arm qemu-system-mips qemu-system-misc qemu-system-ppc qemu-system-sparc qemu-system-x86 && \
    find /usr/lib/python3/dist-packages/ -name '__pycache__' -type d -exec rm -r "{}" + && \
    rm -rf /var/lib/apt/lists/*
