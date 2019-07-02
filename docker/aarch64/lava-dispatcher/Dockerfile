FROM hub.lavasoftware.org/lava/pkg/docker/aarch64/lava-dispatcher-base

ARG pkg_lxc=lava-lxc.deb
COPY $pkg_lxc /tmp/lxc.deb
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
RUN mkdir /root/entrypoint.d
ENTRYPOINT ["/root/entrypoint.sh"]
