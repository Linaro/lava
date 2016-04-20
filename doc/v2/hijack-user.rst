.. _hijack_user:

Switch / Hijack User
====================

The superuser in LAVA can be enabled to hijack or switch and work on
behalf of other users without knowing their credentials. This comes
handy when users report problems in their login and the superuser
wants to reproduce it. This functionality is enabled by django-hijack
module.

.. note:: Once a user is hijacked by the superuser, the hijack remains
          in effect until the superuser logs out of the hijacked user
          in LAVA and logs back in.

django-hijack depends on django-compat and both these modules should
be installed in order to enable this support. These packages are
optional for lava and are not installed by default. They are available
in Debian testing release as of now.

Install `python-django-compat` and `python-django-hijack` packages
directly using apt if either of production-repo or staging-repo are
configured already using `images.validation.linaro.org`
See :ref:`lava_repositories` and :ref:`lava_archive_signing_key`.

Once the above packages are installed, restart apache webserver for
the changes to take effect::

  $ sudo service apache2 restart

Hijack by calling URLs in the browser's address bar
***************************************************

Users can be hijacked directly from the address bar by typing:

 * http://example.com/hijack/email/{email-address}
 * http://example.com/hijack/username/{username}
 * http://example.com/hijack/{user-id}

.. note:: Replace `example.com` with your LAVA instance's hostname.

Read more about django-hijack in
https://github.com/arteria/django-hijack#django-hijack
