FROM hub.lavasoftware.org/lava/pkg/docker/lava-dispatcher-base

ARG pkg_common=lava-common.deb
COPY $pkg_common /tmp/common.deb
RUN dpkg -i /tmp/common.deb && \
    rm -f /tmp/common.deb

ARG pkg_dispatcher=lava-dispatcher.deb
COPY $pkg_dispatcher /tmp/dispatcher.deb
RUN dpkg -i /tmp/dispatcher.deb 7& \
    rm -f /tmp/dispatcher.deb
