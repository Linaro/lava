# syntax=docker/dockerfile:1.2

# Argument for the FROM should be defined before the first stage in multi-stage
# builds while argument used inside a build stage should be defined in tethe
# given build stage.
# See https://github.com/moby/moby/issues/38379#issuecomment-447835596
ARG base_image=""

# Build the documentation
FROM debian:bullseye-slim AS doc
RUN apt-get update && \
    apt-get install --yes --no-install-recommends git make python3-sphinx python3-sphinx-bootstrap-theme
COPY ./lava_common/version.py /app/lava_common/version.py
COPY ./lava_common/VERSION /app/lava_common/VERSION
COPY ./doc/v2 /app/doc/v2
RUN make -C /app/doc/v2 html

# Call the install script in the lava-server-base image
# In fact we use the lavaserver user and group
FROM $base_image as build
ARG lava_version=""
COPY --from=doc /app/doc/v2/_build/html/ /doc
RUN --mount=type=bind,target=/app \
    # Install using setup.py
    cd /app && \
    python3 setup.py build -b /tmp/build egg_info --egg-base /tmp/build install --root /install --no-compile --install-layout=deb lava-common && \
    rm -rf /tmp/build && \
    python3 setup.py build -b /tmp/build egg_info --egg-base /tmp/build install --root /install --no-compile --install-layout=deb lava-coordinator && \
    rm -rf /tmp/build && \
    python3 setup.py build -b /tmp/build egg_info --egg-base /tmp/build install --root /install --no-compile --install-layout=deb lava-server && \
    rm -rf /tmp/build && \
    echo "$lava_version" > /install/usr/lib/python3/dist-packages/lava_common/VERSION && \
    # Create empty files
    touch /install/var/log/lava-server/django.log && \
    # chown/chmod every files
    chown -R lavaserver:lavaserver /install/etc/lava-server/dispatcher-config/ && \
    chown -R lavaserver:lavaserver /install/etc/lava-server/dispatcher.d/ && \
    chown -R lavaserver:lavaserver /install/etc/lava-server/settings.d/ && \
    chown -R lavaserver:lavaserver /install/var/lib/lava-server/default/ && \
    chown -R lavaserver:lavaserver /install/var/lib/lava-server/home/ && \
    chown -R lavaserver:adm /install/var/log/lava-server/ && \
    # Install documentation
    install -d /install/usr/share/lava-server/static/docs/v2/ && \
    cp -R /doc/* /install/usr/share/lava-server/static/docs/v2/ && \
    # Move the static files
    mv /install/usr/lib/python3/dist-packages/lava_results_app/static/lava_results_app/ /install/usr/share/lava-server/static/lava_results_app && \
    mv /install/usr/lib/python3/dist-packages/lava_scheduler_app/static/lava_scheduler_app/ /install/usr/share/lava-server/static/lava_scheduler_app && \
    mv /install/usr/lib/python3/dist-packages/lava_server/static/lava_server/ /install/usr/share/lava-server/static/lava_server && \
    ln -s /usr/lib/python3/dist-packages/django/contrib/admin/static/admin/ /install/usr/share/lava-server/static/admin && \
    ln -s /usr/lib/python3/dist-packages/rest_framework/static/rest_framework/ /install/usr/share/lava-server/static/rest_framework && \
    python3 -m whitenoise.compress /install/usr/share/lava-server/static/ && \
    find /usr/lib/python3/dist-packages/ -name '__pycache__' -type d -exec rm -r "{}" +

# Install the entry point
COPY docker/share/entrypoints/lava-server.sh /install/root/entrypoint.sh
RUN mkdir /install/root/entrypoint.d

# Build the final image
FROM $base_image as install
COPY --from=build /install /

EXPOSE 80 3079 5500 8000 8001

# Activate the apache2 configuration and modules
# TODO: remove apache2 and use only gunicorn
RUN a2dissite 000-default && \
    a2ensite lava-server && \
    a2enmod proxy_http && \
    a2enmod proxy_wstunnel && \
    a2enmod rewrite && \
    a2enmod ssl

ENTRYPOINT ["/root/entrypoint.sh"]
