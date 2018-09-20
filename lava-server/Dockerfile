FROM hub.lavasoftware.org/lava/pkg/docker/lava-server-base

EXPOSE 80
EXPOSE 5500
EXPOSE 5555
EXPOSE 5556

# Install local packages
ARG pkg_common=lava-common.deb
COPY $pkg_common /tmp/common.deb
RUN dpkg -i /tmp/common.deb && \
    rm -f /tmp/common.deb

ARG pkg_server=lava-server.deb
COPY $pkg_server /tmp/server.deb
RUN service postgresql start && \
    dpkg -i /tmp/server.deb && \
    rm -f /tmp/server.deb && \
    lava-server manage shell -c "from django.contrib.auth.models import User; User.objects.create_superuser('admin', 'admin@example.com', 'admin')" && \
    service postgresql stop

ARG pkg_server_doc=lava-server-doc.deb
COPY $pkg_server_doc /tmp/server-doc.deb
RUN dpkg -i /tmp/server-doc.deb && \
    rm -f /tmp/server-doc.deb

# Activate the apache2 configuration and module
run a2dissite 000-default
run a2ensite lava-server && a2enmod proxy_http

# Copy lava settings
COPY settings.conf /etc/lava-server/settings.conf

# Install the entry point
COPY entrypoint.sh /root/
ENTRYPOINT ["/root/entrypoint.sh"]
