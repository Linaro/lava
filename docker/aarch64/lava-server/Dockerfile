ARG base_image=hub.lavasoftware.org/lava/lava/aarch64/lava-server-base
FROM $base_image

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

# As we are using debian slim version we should explicitely list the
# documentation that we want to include.
# By default, only copyright files are kept in /usr/share/doc/
RUN echo "path-include /usr/share/doc/lava-server-doc/html/v2/*" >> /etc/dpkg/dpkg.cfg.d/docker && \
    apt install --yes -t stretch-backports --no-install-recommends /tmp/server-doc.deb && \
    rm -f /tmp/server-doc.deb

ARG pkg_server=lava-server.deb
COPY $pkg_server /tmp/server.deb
RUN service postgresql start && \
    apt install --yes -t stretch-backports --no-install-recommends /tmp/server.deb && \
    rm -f /tmp/server.deb && \
    service postgresql stop

# Activate the apache2 configuration and modules
RUN a2dissite 000-default && \
    a2ensite lava-server && \
    a2enmod proxy_http && \
    a2enmod expires && \
    a2enmod headers

# Copy lava settings
COPY settings.conf /etc/lava-server/settings.conf

# Install the entry point
COPY entrypoint.sh /root/
RUN mkdir /root/entrypoint.d
ENTRYPOINT ["/root/entrypoint.sh"]
