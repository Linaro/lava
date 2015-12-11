.. index:: support

.. _getting_support:

Getting support
###############

LAVA is free software and is provided "as is" without warranty of any
kind. Support is offered using the methods below and we will try to
help resolve queries.

Whenever you look for support for LAVA, there are some guidelines
to follow:

.. index::
   single: pastebin
   single: support guidelines

.. _guidelines:

Guidelines
**********

* Avoid putting LAVA job output directly into your email to a list or
  IRC channel. Mailing list posts can include a few lines but not IRC.
* If you are using the current dispatcher, (not the :term:`refactoring`),
  you need to **always** re-run your test with ``logging_level: DEBUG`` if
  you have not done so already.
* Always use a `pastebin`_ for log output and include a link
  to the paste in your post. Pastebins can be provided by your
  distribution or other sources - the internal Linaro pastebin requires
  the user to :ref:`register`. Example pastebins which are open to
  anyone include `pastebin.com <http://pastebin.com/>`_ and
  `paste.debian.net <https://paste.debian.net/>`_. Pastes will typically
  expire automatically, depending on the option selected by the user
  making the paste.
* Paste from the complete log, not the summary, so that you get the
  complete lines.
* Include in this paste or another paste, the job definition you used.
* Provide details of which server you are using (with a URL
  if it is publicly visible or a version string from the documentation
  pages if not) and details of the actual device(s) in use.

.. _pastebin: https://en.wikipedia.org/wiki/Pastebin

.. index:: mailing list

.. _mailing_lists:

Mailing lists
*************

The primary method for support for LAVA is based on mailing lists.

A few guidelines apply to all such lists:

* Reply to the list, adding the submitter in CC where appropriate.
* If your job uses URLs which are not visible to the rest of the list,
  include a rough outline of how those were built and what versions of tools
  were used.
* Avoid `top posting <https://en.wikipedia.org/wiki/Posting_style#Top-posting>`_.
* Always provide as much context as you can when phrasing your question
  to the list.

.. index:: lava-users support

.. _lava_users:

lava-users
==========

The `lava-users <https://lists.linaro.org/mailman/listinfo/lava-users>`_
mailing list concentrates on support for current LAVA tests, involving
test writers, individual admins and LAVA developers. Users are
encouraged to contribute to answer queries from other users.

.. index:: lava-devel support

.. _lava_devel:

lava-devel
==========

``lava-devel`` is an alias to `linaro-validation <https://lists.linaro.org/mailman/listinfo/linaro-validation>`_
and is aimed at supporting test writers and admins who are adapting to the
:term:`pipeline` support and discussions relating to announcements from the
LAVA developers. Replies to the :ref:`lava_announce` list are directed here.

.. index:: lava-announce list

.. _lava_announce:

lava-announce
=============

Subscribing to the `lava-announce <https://lists.linaro.org/mailman/listinfo/lava-announce>`_
list is recommended for **everyone** using LAVA, whether a test writer or
viewing reports or administering a LAVA instance.

As the :term:`refactoring` continues, it will become increasingly important
that **all** users of LAVA are aware of the upcoming changes, new methods
available in the refactoring and the removal of old methods.

Replies to this list are sent to the :ref:`lava_devel` list - if you are
not subscribed to ``lava-devel``, please ask other uses to CC you on
replies.

.. index:: irc

IRC
***

See also :ref:`development_process`.

`IRC <https://en.wikipedia.org/wiki/Internet_Relay_Chat>`_ is a common
support method for developers. Our team is spread geographically around
the world, with some members in Europe, America, Asia. We
are usually talking on our IRC channel ``#linaro-lava`` on
``irc.freenode.net``.

:ref:`guidelines` apply to IRC as well:

* Use a proxy or other service which keeps you connected to IRC. Developers
  are based in multiple timezones and not everyone can answer all queries.
  Therefore, you may have to wait several hours until the relevant
  person or people are awake. Check back for replies on the channel
  intermittently. If you disconnect, you will **not** see any replies
  sent whilst you were disconnected from the channel.
* Ask your question, do not wait to see people joining or talking.
* As with mailing lists, it is even more important with IRC that you
  **always** use a pastebin. See :ref:`guidelines`.
* Do not assume that the person someone else spoke to last is also able
  to answer your question.
* Do not assume that the person you spoke to last is also able to answer
  your other question(s).
* Reply directly to a person by putting their IRC nickname at the
  start of your message to the channel. In a busy channel, it can be hard
  to spot replies not made to you.
* Developers are busy - IRC is part of our development process, so please
  be considerate of the amount of time involved, there is code to write
  and there are bug fixes to make for other users as well.
* Avoid personal messages unless there is a clear privacy issue involved
  or you know the person well.
* You may well find that one of the :ref:`mailing_lists` actually provides
  a faster answer to your question, especially if you are new to LAVA.
