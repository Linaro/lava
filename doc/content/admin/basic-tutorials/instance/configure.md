# Configure LAVA

## Creating a superuser

Admins can create superuser accounts on the command line:

!!! example ""

    ```shell tab="Docker"
    docker-compose exec lava-server lava-server manage createsuperuser
    ```

    ```shell tab="Debian"
    lava-server manage createsuperuser
    ```
