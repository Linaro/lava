# Synchronizing records from device dictionary

LAVA has the ability to synchronize database records with the device
dictionary. It currently supports these models:

* Device
* Device type
* Tag
* Alias
* Physical Owner
* Physical Group
* Group Device Permissions

This can make administration less cumbersome and can help with Ansible and
similar setups. By using this feature administrators are able to keep the list
of these records inside the version control.

For device records, a flag named **is_synced** is used to recognize devices
which are synced to/from the device dictionary. This option can be updated via
usual channels (web UI admin, APIs).

Once the new device dictionary is added to the filesystem it needs to include
the following dictionary variable which will control which records should be
created:

```jinja
{% set sync_to_lava = {
   "device_type": "qemu",
   "worker": "worker-01"
   "tags": ["tag1", "tag2"],
   "aliases": ["alias1", "alias2"],
   "physical_owner": "owner-01",
   "physical_group": "group-01",
   "group_device_permissions": [
       ["change_device", "group-02"],
       ["view_device", "group-02"],
       ["submit_to_device", "group-02"],
   ]
   }
%}
```

A management command is used to perform a sync to the database:

=== "Debian"
    ```shell
    lava-server manage sync
    ```

=== "docker-compose"
    ```shell
    docker-compose exec lava-server lava-server manage maintenance
    ```

You can for example set this to run when the contents of the device dictionary
folder change using a watch utility.

In the above example, a system will create:

* device named after the device dictionary file
* device type named qemu (if it doesn't exist already) and relate this device to it
* worker named worker-01 (if it doesn't exist already) and relate this device to it
* aliases in the list; and relate them to the specified device type
* tags in the list; and relate them to the device
* relate specified physical owner (existed) to the device
* relate specified physical group (existed) to the device
* assign/delete group device permissions to the device

If at any point the device dictionary is removed (and once the sync command is
executed) the system will move the device that was created to it to **Retired**
health. If all the devices of the synced device type are **Retired** that
particular device type will be marked as invisible in the system.
