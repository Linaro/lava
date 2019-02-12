FROM hub.lavasoftware.org/lava/pkg/docker/aarch64/lava-server-base

EXPOSE 80
EXPOSE 5500
EXPOSE 5555
EXPOSE 5556

RUN apt -q update

# Remove the -t option to apt when porting to buster.

# Install local packages (stretch-backports)
ARG pkg_common=lava-common.deb
COPY $pkg_common /tmp/common.deb
RUN apt install --yes -t stretch-backports --no-install-recommends /tmp/common.deb && \
    rm -f /tmp/common.deb

ARG pkg_server_doc=lava-server-doc.deb
COPY $pkg_server_doc /tmp/server-doc.deb
RUN apt install --yes -t stretch-backports --no-install-recommends /tmp/server-doc.deb && \
    rm -f /tmp/server-doc.deb

ARG pkg_server=lava-server.deb
COPY $pkg_server /tmp/server.deb
RUN service postgresql start && \
    apt install --yes -t stretch-backports --no-install-recommends /tmp/server.deb && \
    rm -f /tmp/server.deb && \
    service postgresql stop

# Activate the apache2 configuration and module
RUN a2dissite 000-default && \
    a2ensite lava-server && \
    a2enmod proxy_http

# Copy lava settings
COPY settings.conf /etc/lava-server/settings.conf

# Install the entry point
COPY entrypoint.sh /root/
RUN mkdir /root/entrypoint.d
ENTRYPOINT ["/root/entrypoint.sh"]
