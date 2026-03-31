# Contribution Guide

We want to make it as easy as possible for LAVA Software users to become
LAVA Software Community Project contributors, so we have created this
guide to help you get started.

The LAVA Software Community Project has published this Contribution
Guide, and all contributors will be expected to adhere to these
guidelines when submitting issues or merge requests. They are designed
to clarify the requirements for contributions, to make contributing more
efficient for all involved.

Following the guidelines is a great way to prevent your contributions
from being rejected or delayed. Most maintainers won't intend to
discredit your work or be tough on contributors. However, many are busy
and some may be working on LAVA in their free time. Well-formed
contributions are much easier to review and work with.

!!! info "See also"
    - [Code of Conduct](../code-of-conduct.md)
    - [Contributing Process](../tutorials/contributing.md)

### Conflicting priorities

Sometimes a request will be turned down because of conflicting
priorities. It is important to talk about the reasons on the mailing
list. Whether you're requesting a new feature, or providing a fix,
remember that the maintainer has to weigh up your contribution. They are
the people who may have to support the new code in the future, and
resources are often scarce. Try not to be discouraged if your feature
request or merge request is turned down. Be open-minded and, if
necessary, propose an alternative idea on the mailing list after hearing
their concerns.

## Pre-requisites to start

* LAVA is written in [Python](http://www.python.org/), so you will need
  to know (or be willing to learn) the language.
* The web interface is a [Django](https://www.djangoproject.com/)
  application so you will need to use and debug Django if you need to
  modify the web interface.
* LAVA uses [YAML][yaml] heavily internally, so you'll likely need to
  understand the syntax.
* LAVA also uses [Jinja2][jinja2].
* All LAVA software is maintained in [git](https://www.git-scm.org/).
* Some familiarity with [Debian](https://www.debian.org/) is going to be
  useful; helper scripts are available when preparing updated `.deb`
  packages based on your modifications.

LAVA is complex and designed to solve complex problems. This has
implications for how LAVA is developed, tested, deployed and used.

## Other elements involved

* The Django backend used with LAVA is
  [PostgreSQL](https://www.postgresql.org/).
* The LAVA UI includes JavaScript and CSS.
* LAVA also uses [ZMQ](http://zeromq.org/) and XML-RPC.

In addition, test jobs and device support can involve use of U-Boot,
GuestFS, fastboot, ADB, QEMU, Grub, SSH, Docker, and a wide variety
of other systems and tools.

## Updating documentation

We welcome contributions to improve our documentation. If you are
considering adding new features to LAVA or changing current behavior,
also please ensure that the changes include matching updates for the
documentation.

Wherever possible, all new sections of documentation should come
**with worked examples**.

* If the change relates to or includes particular test definitions to
  demonstrate the new support, add a test definition YAML file as an
  example.
* Use comments in the examples and link to existing terms and sections.

--8<-- "refs.txt"
