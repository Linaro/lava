# syntax=docker/dockerfile:1.2

# Argument for the FROM should be defined before the first stage in multi-stage
# builds while argument used inside a build stage should be defined in tethe
# given build stage.
# See https://github.com/moby/moby/issues/38379#issuecomment-447835596
ARG base_image=""

# Call the install script in a empty image
FROM debian:bullseye-slim as build
ARG lava_version=""
RUN apt-get update && \
    apt-get install --no-install-recommends --yes python3 python3-distutils python3-setuptools

# Install lava-lxc-mocker
COPY lava/lxc-mocker/ /install/usr/bin/

# Install common, dispatcher and dispatcher-host modules
RUN --mount=type=bind,target=/app \
    cd /app && \
    python3 setup.py build -b /tmp/build egg_info --egg-base /tmp/build install --root /install --no-compile --install-layout=deb lava-common && \
    rm -rf /tmp/build && \
    python3 setup.py build -b /tmp/build egg_info --egg-base /tmp/build install --root /install --no-compile --install-layout=deb lava-dispatcher && \
    rm -rf /tmp/build && \
    python3 setup.py build -b /tmp/build egg_info --egg-base /tmp/build install --root /install --no-compile --install-layout=deb lava-dispatcher-host && \
    rm -rf /tmp/build && \
    echo "$lava_version" > /install/usr/lib/python3/dist-packages/lava_common/VERSION

# Install the entry point
COPY docker/share/entrypoints/lava-dispatcher.sh /install/root/entrypoint.sh
RUN mkdir /install/root/entrypoint.d

# Build the final image
FROM $base_image as install
COPY --from=build /install /

ENTRYPOINT ["/root/entrypoint.sh"]
