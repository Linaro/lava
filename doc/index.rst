lava-server for Debian
======================

To install all of LAVA on a single machine, use:

 $ sudo apt-get install postgresql postgresql-9.1
 $ sudo ## add linaro repository
 $ sudo apt-get update
 $ sudo apt-get install lava

See also http://wiki.debian.org/LAVA

LAVA Components
^^^^^^^^^^^^^^^

=============== =========================================
lava            meta-package for single instance setup
lava-server     apache and WSGI settings and HTML content
lava-scheduler  scheduling daemon
lava-dispatcher dispatches jobs to devices
=============== =========================================

lava-server recommends lava-scheduler & lava-dispatcher
	checks for each and disables/enables in config
	provides WSGI and apache conf files

Packages use a "default" instance but allow for other instances, possibly.
(at least, don't prevent other instances.)
	Limitations: /usr/share/lava-server/templates
		(was "$LAVA_PREFIX/$LAVA_INSTANCE/code/current/server_code/templates/")
		per instance run sockets for uwsgi
		/var/log/lava-uwsgi.log

Need to prevent taking over the default apache site unless desired.
    sudo a2ensite $LAVA_INSTANCE.conf
#    sudo a2dissite 000-default || true
    sudo service apache2 restart


Layout:
$LAVA_PREFIX/$LAVA_INSTANCE/etc/lava-server/settings.conf

	/etc/lava-server/default/settings.conf

Media: tracked in db, so needs to be /var/lib/, not cache or log/

lava-deployment-tool changes:
	wizard_config_app done automatically by what is installed.
	install_database & wizard_database: dbconfig-common
    # Create database configuration file
    /etc/lava-server/default_database.conf 
	lava sys user -> lava (debconf default)
	Need a perl script to process /etc/lava/default/instance.conf (_save_config)
	install /etc/lava-server/settings.conf
