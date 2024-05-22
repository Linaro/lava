#!/bin/sh -e
#
# Copyright (C) 2020-present Linaro Limited
#
# Author: Chase Qi <chase.qi@linaro.org>
#
# SPDX-License-Identifier: GPL-2.0-or-later

INSTALL="docker_worker"
SERVER=""
NAME=""
TOKEN=""

# shellcheck disable=SC1091
. /etc/os-release

usage() {
    echo "Usage: $0 [-i <docker_worker|worker|dut_services>] [-s <server_url>] [-n <worker_name>] [-t <worker_token>]" 1>&2
    exit 1
}

while getopts "i:s:n:t:h" opt; do
    case "$opt" in
        i) INSTALL="${OPTARG}" ;;
        s) SERVER="${OPTARG}" ;;
        n) NAME="${OPTARG}" ;;
        t) TOKEN="${OPTARG}" ;;
        h|*) usage ;;
    esac
done

info_msg() {
    printf "INFO: %s\n" "$1" >&1
}

error_msg() {
    printf "ERROR: %s\n" "$1" >&2
    exit 1
}

install_pkgs() {
  apt-get update -qy
  # shellcheck disable=SC2086
  DEBIAN_FRONTEND=noninteractive apt-get install -q -y $1
}

add_apt_repo() {
  wget -O /etc/apt/trusted.gpg.d/lavasoftware.key.asc https://apt.lavasoftware.org/lavasoftware.key.asc
  echo "deb https://apt.lavasoftware.org/release ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/lava.list
}

config_worker() {
  case "${INSTALL}" in
    docker_worker) config="/etc/lava-dispatcher-host/lava-docker-worker" ;;
    worker) config="/etc/lava-dispatcher/lava-worker" ;;
  esac

  if [ -n "${SERVER}" ]; then
    sed -i '/^URL=/d' "${config}"
    echo "URL=\"${SERVER}\"" >> "${config}"
  fi

  if [ -n "${NAME}" ]; then
    sed -i '/^WORKER_NAME=/d' "${config}"
    echo "WORKER_NAME=\"--name ${NAME}\"" >> "${config}"
  fi

  if [ -n "${TOKEN}" ]; then
    sed -i '/^TOKEN=/d' "${config}"
    echo "TOKEN=\"--token ${TOKEN}\"" >> "${config}"
  fi

  case "${INSTALL}" in
    docker_worker)
      systemctl enable lava-docker-worker.service
      systemctl restart lava-docker-worker.service
      ;;
    worker)
      systemctl restart lava-worker.service
      ;;
  esac
}

install_dut_services() {
  install_pkgs "apache2 tftpd-hpa nfs-kernel-server ser2net"

  # config apache2.
  wget -O /etc/apache2/sites-available/lava-dispatcher.conf https://gitlab.com/lava/lava/-/raw/master/share/apache2/lava-dispatcher.conf?ref_type=heads
  a2dissite 000-default
  a2ensite lava-dispatcher
  systemctl restart apache2

  # config nfs server.
  echo "/var/lib/lava/dispatcher/tmp *(rw,no_root_squash,async,no_subtree_check)" > /etc/exports
}

install_worker() {
  install_pkgs "wget"
  add_apt_repo

  case "${INSTALL}" in
    docker_worker) install_pkgs "docker.io lava-dispatcher-host" ;;
    worker) install_pkgs "lava-dispatcher" ;;
    dut_services) ;;
    *) error_msg "Installing ${INSTALL} is not supported." ;;
  esac

  config_worker
}

info_msg "Installing LAVA ${INSTALL} ..."
[ "$(id -ru)" -ne 0 ] && error_msg "Please run the script as root or using sudo."
[ "${ID}" != "debian" ] && error_msg "Not supported on non-Debian OS."
[ "${VERSION_CODENAME}" != "bookworm" ] && error_msg "Only Debian bookworm is supported."
if [ "${INSTALL}" = "dut_services" ]; then
  install_dut_services
else
  install_worker
fi
info_msg "LAVA ${INSTALL} installation finished correctly."
