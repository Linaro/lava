echo "Setting up development database..."

lava_instance_user=devel
lava_password=devel
lava_database=devel

echo "Dropping old database and user"
sudo -u postgres dropdb $lava_database
sudo -u postgres dropuser $lava_instance_user

echo "Creating new user and database"
# Create database user
sudo -u postgres createuser \
    --no-createdb \
    --encrypted \
    --login \
    --no-superuser \
    --no-createrole \
    --no-password \
    $lava_instance_user

# Set a password for our new user
sudo -u postgres psql \
    --quiet \
    --command="ALTER USER \"$lava_instance_user\" WITH PASSWORD '$lava_password'"

# Create a database for our new user
sudo -u postgres createdb \
    --encoding=UTF-8 \
    --owner=$lava_instance_user \
    --no-password \
    $lava_database
