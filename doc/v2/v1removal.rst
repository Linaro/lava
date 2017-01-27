.. index:: V1 removal

.. _v1_removal:

Removal of V1 data objects
##########################

This page is to help administrators of LAVA instances handle the upgrade of
``lava-server`` which causes the **DELETION of ALL V1 test data**. Admins have
the choice of aborting the installation of this upgrade to protect the V1 test
data with the proviso that **no** further updates of LAVA will be possible on
such instances. Support for LAVA V1 ended with the block on submission of V1
test jobs in the 2017.10 release. All future releases of LAVA will only contain
V2 code and will only be able to access V2 test data. If admins choose to keep
an instance to act as an archive of V1 test data, that instance **must** stay
on the **2017.10** release of LAVA.

.. seealso:: :ref:`v1_end_of_life`

.. danger:: Upgrades normally try to avoid removal of data but this upgrade
   **deliberately drops the V1 data tables permanently**. Whilst this procedure
   has been tested, there is no guarantee that all instances will manage the
   removal of the V1 test data cleanly. It is strongly recommended that all
   instances have a usable :ref:`backup <admin_backups>` before proceeding.

   **DO NOT INTERRUPT this upgrade**. If anything goes wrong with the upgrade,
   **STOP IMMEDIATELY** and refer to this page, then :ref:`contact us
   <getting_support>`.

   At all costs, avoid running commands which activate or execute any further
   migration operation, especially ``lava-server manage migrate`` and
   ``lava-server manage makemigrations``. Remember that removing, purging or
   reinstalling the ``lava-server`` package without fixing the database will
   **not** fix anything as it will attempt to run more migrations. Even if you
   find third party advice to run such commands, **do not do so** without
   :ref:`talking to the LAVA software team <getting_support>`.

   It remains possible to escalate a failed upgrade into a **complete data
   loss** of V1 and V2 test data by trying to fix a broken system. In the event
   of a failed upgrade, the LAVA software team may advise you to restore from
   backup and then determine if there are additional steps which can be taken
   to allow the upgrade to complete, instead of attempting to fix the breakage
   directly. Without a backup, your only option may be to start again with a
   completely fresh installation with no previous test jobs, no users and no
   configured devices.

Maintenance window
******************

It is recommended that all instances declare a scheduled **maintenance window**
before starting this upgrade. Take all devices offline and wait for all running
test jobs to finish. For this upgrade is it also important to replace the
``lava-server`` apache configuration with a temporary holding page for all URLs
related to the instance, so that users get a useful page instead of an error.
This prevents accidental accesses to the database during any later recovery
work and also prevents new jobs being submitted.

.. _removing_v1_files:

Removing V1 files after the upgrade
***********************************

After a successful upgrade to 2017.12, the following V1 components will still
exist:

* V1 ``TestJob`` database objects (definition(s), status, submitter, device
  etc.)

* V1 test job log files in ``/var/lib/lava-server/default/media/job-output/``

* V1 bundles as JSON files in ``/var/lib/lava-server/default/media/bundles/``

* V1 attachments in ``/var/lib/lava-server/default/media/attachments/``

* Configuration files in ``/etc/init.d/``::

   /etc/init.d/lava-master*
   /etc/init.d/lava-publisher*
   /etc/init.d/lava-server*
   /etc/init.d/lava-server-gunicorn*
   /etc/init.d/lava-slave*

To delete the test job log files and the ``TestJob`` database objects, use the
``lava-server manage`` helper:

.. code-block:: none

  $ sudo lava-server manage jobs rm --older-than 0d --v1

Bundles and attachments can be deleted simply by removing the directories:

.. code-block:: none

 $ sudo rm -rf /var/lib/lava-server/default/media/bundles
 $ sudo rm -rf /var/lib/lava-server/default/media/attachments

.. index:: V1 removal - abort

.. _aborting_v1_removal:

Aborting the upgrade
********************

If you have read `the roadmap to removal of V1
<https://lists.linaro.org/pipermail/lava-announce/2017-September/000037.html>`_
and still proceeded with the upgrade to ``2017.12`` but then decide to abort,
there is **one** safe chance to do so, when prompted at the very start of the
install process with the following prompt::

 Configuring lava-server

 If you continue this upgrade, all V1 test data will be permanently DELETED.

 V2 test data will not be affected. If you have remaining V1 test data that you
 care about, make sure it is backed up before you continue here.

 Remove V1 data from database?

If you have answered **YES** to that prompt, **there is no way to safely abort
the upgrade**. You **must** proceed and then :ref:`recover from a backup
<admin_restore_backup>` if something goes wrong or you want to keep that
instance on a version of LAVA which no longer receives updates.

.. caution:: Many configuration management systems hide such prompts, to allow
   for smooth automation, by setting environment variables. **There is nothing
   LAVA can do to prevent this** and it is **not** a bug in LAVA when it
   happens.

What happens if I choose to abort?
**********************************

The system will continue operating with the existing version of LAVA from
before the upgrade was attempted. The upgrade will still be available and you
will be asked the question again, each time the package tries to upgrade. You
may want to use ``apt-mark hold lava-server`` to prevent ``apt`` considering
the newer version as an upgrade.

What happens if the LAVA package upgrade fails?
***********************************************

**STOP HERE!**
==============

.. warning:: Do not make **any** attempt to fix the broken system without
   :ref:`talking to us <getting_support>`. Put the full error messages and the
   command history into a pastebin and attach to an email to the lava-users
   mailing list. It is generally unhelpful to attempt to fix problems with this
   upgrade over IRC.

The system will be left with a ``lava-server`` package which is not completely
installed. ``apt`` will complain when further attempts are made to install any
packages (and will try to complete the installation), so take care on what
happens on that instance from here on.

#. Record the complete and exact error messages from the master. These may
   scroll over a few pages but **all** the content will be required.

#. Record the history of **all** commands issued on the master recently.

#. Declare an **immediate** maintenance window or tell all users any current
   window must be extended. Disable all access to the complete instance. For
   example, set up routing to prevent the apache service from responding on the
   expected IP address and virtual host details to avoid confusing users. Place
   a holding page elsewhere until the installation is fully complete and
   tested.

   .. caution:: Users must **not** be allowed to access the instance whilst
      recovery from this failure is attempted. There must be **no** database
      accesses outside the explicit control of the admin attempting the
      recovery.

   Complete downtime is the **only** safe way to attempt to fix the problems.

#. Assure yourself that a suitable, tested, backup already exists.
