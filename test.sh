#!/usr/bin/env bash
# Copyright (C) 2026 Qualcomm Technologies, Inc. and/or its subsidiaries.
#
# SPDX-License-Identifier: GPL-2.0-or-later

set -eu
cd "$(dirname "$0")"  # scripts below use repo-root-relative paths

./docker/share/generate.py

podman build --no-cache \
  -t lava-server-base:bootstrap5 \
  -f docker/lava-server-base/Dockerfile .

podman build --no-cache \
  -t lava-server:bootstrap5 \
  --build-arg base_image=lava-server-base:bootstrap5 \
  --build-arg lava_version="2029.10" \
  -f docker/lava-server/Dockerfile .

podman run --rm -it -p 127.0.0.1:8080:80 \
  -e LAVA_ADMIN_USERNAME=admin \
  -e LAVA_ADMIN_PASSWORD=admin \
  -v "$PWD/test-data.sh:/root/entrypoint.d/90-test-data.sh:ro" \
  lava-server:bootstrap5

# lava server should now be available on http://localhost:8080/
# (sign in with admin/admin; dummy jobs are seeded by test-data.sh)
