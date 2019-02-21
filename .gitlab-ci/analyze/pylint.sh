#!/bin/sh

set -e

if [ "$1" = "setup" ]
then
  set -x
  apt-get -q update
  apt-get install --no-install-recommends --yes pylint3 python3-pylint-django
else
  set -x
  # Only run some pylint checkers
  # See https://docs.pylint.org/en/1.6.0/features.html
  # Disabled:
  #  C0411: %s comes before %s Used when PEP8 import order is not respected (standard imports first, then third-party libraries, then local imports)
  #  C0412: Imports from package %s are not grouped
  #  E0401: Unable to import '%s'
  #  E0611: No name '%s' in module '%s'
  #  R0201: Method could be a function
  #  R0401: Cyclic import (%s -> %s)
  # Enabled:
  #  W0404: Reimport %r (imported line %s) Used when a module is reimported multiple times.
  #  W1505: Using deprecated method warn()
  #  W0611: Unused %s Used when an imported module or variable is not used.
  pylint3 --disable=all --enable=elif,exceptions,stdlib,imports,variables,string,string_constant,logging,newstyle,classes --disable=C0411,C0412,E0401,E0611,R0201,R0401,W --enable=W0404,W1505,W0611 --ignore=lava/coordinator lava lava_common lava_dispatcher lava_rest_app lava_results_app lava_scheduler_app lava_server linaro_django_xmlrpc share
fi
