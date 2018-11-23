FROM hub.lavasoftware.org/lava/pkg/docker/amd64/lava-dispatcher-base

ARG pkg_common=lava-lxc.deb
COPY $pkg_common /tmp/lxc.deb
RUN dpkg -i /tmp/lxc.deb && \
    rm -f /tmp/lxc.deb

ARG pkg_common=lava-common.deb
COPY $pkg_common /tmp/common.deb
RUN dpkg -i /tmp/common.deb && \
    rm -f /tmp/common.deb

ARG pkg_dispatcher=lava-dispatcher.deb
COPY $pkg_dispatcher /tmp/dispatcher.deb
RUN dpkg -i /tmp/dispatcher.deb && \
    rm -f /tmp/dispatcher.deb

# Install the entry point
COPY entrypoint.sh /root/
ENTRYPOINT ["/root/entrypoint.sh"]
