import base64
import errno
import os
import pickle  # nosec - migration no longer in active use
import pprint

from django.db import migrations


def devicedictionary_to_jinja2(data_dict, extends):
    """
    Formats a DeviceDictionary as a jinja2 string dictionary
    Arguments:
        data_dict: the DeviceDictionary.to_dict()
        extends: the name of the jinja2 device_type template file to extend.
        (including file name extension / suffix) which jinja2 will later
        assume to be in the jinja2 device_types folder
    """
    if not isinstance(data_dict, dict):
        return None
    pp = pprint.PrettyPrinter(indent=0, width=80)  # simulate human readable input
    data = "{%% extends '%s' %%}\n" % extends
    for key, value in data_dict.items():
        if key == "extends":
            continue
        data += "{%% set %s = %s %%}\n" % (str(key), pp.pformat(value).strip())
    return data


def revert_migrate_device_dict_to_filesystem(apps, schema_editor):
    pass


def migrate_device_dict_to_filesystem(apps, schema_editor):
    # Get the right version of the models
    Device = apps.get_model("lava_scheduler_app", "Device")
    DeviceDictionaryTable = apps.get_model(
        "lava_scheduler_app", "DeviceDictionaryTable"
    )
    dd_dir = "/etc/lava-server/dispatcher-config/devices"

    # Create the directory
    try:
        os.mkdir(dd_dir, 0o755)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            pass

    # Load the device dictionaries
    DDT = {}
    for device_dict in DeviceDictionaryTable.objects.all():
        hostname = device_dict.kee.replace(
            "__KV_STORE_::lava_scheduler_app.models.DeviceDictionary:", ""
        )
        value64 = device_dict.value
        valuepickled = base64.b64decode(value64)
        value = pickle.loads(valuepickled)  # nosec - no longer in active use
        DDT[hostname] = devicedictionary_to_jinja2(
            value["parameters"], value["parameters"]["extends"]
        )

    # Dump the device dictionaries to file system
    for device in Device.objects.filter(is_pipeline=True).order_by("hostname"):
        if device.hostname not in DDT:
            print("Skip %s" % device.hostname)
            continue

        device_dict = DDT[device.hostname]
        with open(os.path.join(dd_dir, "%s.jinja2" % device.hostname), "w") as f_out:
            f_out.write(device_dict)


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0026_devicetype_disable_health_check")]

    operations = [
        migrations.RunPython(
            migrate_device_dict_to_filesystem,
            revert_migrate_device_dict_to_filesystem,
            elidable=True,
        ),
        migrations.DeleteModel(name="PipelineStore"),
        migrations.DeleteModel(name="DeviceDictionaryTable"),
    ]
