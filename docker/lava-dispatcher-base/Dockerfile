FROM debian:buster-slim

LABEL maintainer="Rémi Duraffort <remi.duraffort@linaro.org>"

ENV DEBIAN_FRONTEND noninteractive

RUN echo 'deb http://deb.debian.org/debian buster-backports main' > /etc/apt/sources.list.d/backports.list && \
    mkdir -p /usr/share/man/man1 /usr/share/man/man7 && \
    apt-get update -q && \
    apt-get install --no-install-recommends --yes wget gnupg ca-certificates && \
    wget https://download.docker.com/linux/debian/gpg && \
    apt-key add gpg && \
    rm gpg && \
    echo "deb https://download.docker.com/linux/debian buster stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update -q && \
    apt-get install --no-install-recommends --yes python3-voluptuous python3-yaml && \
    apt-get install --no-install-recommends --yes bmap-tools python3-aiohttp python3-configobj python3-guestfs python3-jinja2 python3-magic python3-netifaces python3-pexpect python3-pyudev python3-requests python3-setproctitle python3-tz python3-yaml && \
    apt-get install --no-install-recommends --yes android-sdk-libsparse-utils dfu-util git libguestfs-tools qemu-system-arm qemu-system-x86 ser2net telnet tftpd-hpa u-boot-tools unzip xz-utils zstd && \
    apt-get install --no-install-recommends --yes docker-ce-cli && \
    apt-get purge --yes wget gnupg && \
    apt-get autoremove --purge --yes && \
    rm /etc/apt/sources.list.d/docker.list && \
    apt-get update -q && \
    find /usr/lib/python3/dist-packages/ -name '__pycache__' -type d -exec rm -r "{}" + && \
    rm -rf /var/lib/apt/lists/*
