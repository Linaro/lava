# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations, transaction
from lava_scheduler_app import utils


def forwards_func(apps, schema_editor):
    Worker = apps.get_model("lava_scheduler_app", "Worker")
    db_alias = schema_editor.connection.alias
    # Identify master node and populate the required fields.
    # Since migrations run only on master node, we assume the current node
    # should be designated as master.
    is_master = True
    localhost = utils.get_fqdn()
    ipaddr = utils.get_ip_address()

    # NOTE: RPC2_URL formed below is a guess. The administrator should
    #       revisit the correctness of this URL from the administration
    #       UI, fixing it for the node which is designated as the master.
    rpc2_url = "http://{0}/RPC2".format(localhost)

    if localhost == 'example.com' or localhost == 'www.example.com':
        rpc2_url = "http://{0}/RPC2".format(ipaddr)

    try:
        with transaction.atomic():
            worker, created = Worker.objects.using(db_alias).get_or_create(
                hostname=localhost)
            worker.is_master = is_master
            worker.ip_address = ipaddr
            worker.rpc2_url = rpc2_url
            worker.save()
    except:
        print "Identifying master node failed ..."


def backwards_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('lava_scheduler_app', '0002_add_lava-health_user'),
    ]

    operations = [
        migrations.RunPython(
            forwards_func,
            backwards_func,
        ),
    ]
