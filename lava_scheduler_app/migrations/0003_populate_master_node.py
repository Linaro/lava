from django.db import migrations, transaction


def forwards_func(apps, schema_editor):
    Worker = apps.get_model("lava_scheduler_app", "Worker")
    db_alias = schema_editor.connection.alias
    # Identify master node and populate the required fields.
    # Since migrations run only on master node, we assume the current node
    # should be designated as master.
    is_master = True
    localhost = "example.com"
    ipaddr = "0.0.0.0"

    # NOTE: RPC2_URL formed below is a guess. The administrator should
    #       revisit the correctness of this URL from the administration
    #       UI, fixing it for the node which is designated as the master.
    rpc2_url = f"http://{localhost}/RPC2"

    if localhost in ["example.com", "www.example.com"]:
        rpc2_url = f"http://{ipaddr}/RPC2"

    try:
        with transaction.atomic():
            worker, created = Worker.objects.using(db_alias).get_or_create(
                hostname=localhost
            )
            worker.is_master = is_master
            worker.ip_address = ipaddr
            worker.rpc2_url = rpc2_url
            worker.save()
    except Exception:
        print("Identifying master node failed ...")


def backwards_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("lava_scheduler_app", "0002_add_lava-health_user")]

    operations = [migrations.RunPython(forwards_func, backwards_func, elidable=True)]
