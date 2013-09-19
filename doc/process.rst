Development process
===================

LAVA development process is based on Launchpad. If you are not familiar with
that system you should read the https://help.launchpad.net/ guide first. This
guide also includes the basics of Bazaar, our version control system of choice.

Most of the work is done by the members of the Linaro Validation Team (you can
learn more about this team, in particular here:
launchpad.net/~linaro-validation). Having said that, the code is free and open
source software, we welcome third party contributions and new team members.

Our team is spread geographically around the world, with some members in
Europe, America, Asia and Oceania. We are usually talking on our IRC channel
#linaro-lava.


Release process
^^^^^^^^^^^^^^^

LAVA is being developed on a monthly release schedule. Each release is tagged
around 20th of each month. We publish all our releases on pypi (for actual
consumption, packaging, installation, etc.) and Launchpad (for reference).

Launchpad release tarballs are following our YYYY.MM (year, month) pattern.
Should we need to release an upgrade to any existing release (such as a
critical bug fix) we append a sequential number preceded by a dash
(YYYY.MM-NN).

Our PyPi releases use sensible version numbers instead. In general we use
MAJOR.MINOR.MICRO pattern (where MICRO is omitted when zero). Some components
are post 1.0, that is they have a major version greater than zero. For such
components we take extra care to ensure API stability, with sensible transition
periods, deprecation warnings and more. For other components (that have zero as
a major release number) our strategy is to keep them compatible as much as
possible but without ensuring a third party developer code would still work on
each upgrade.


Reporting Bugs
^^^^^^^^^^^^^^

New bugs can be reported here https://bugs.launchpad.net/lava/+filebug.

If you are not sure which component is affected simply report it to any of the
LAVA sub-projects and let us handle the rest. As with any bug reports please
describe the problem and the version of LAVA you ware using.

If you were using our public LAVA instance, the one used by Linaro for daily
activities (http://validation.linaro.org) try to include a link to a page
that manifests the problem as that makes debugging easier.


Patches, fixes and code
^^^^^^^^^^^^^^^^^^^^^^^

If you'd like to offer a patch (whether it is a bug fix, documentation update,
new feature or even a simple typo) it is best to follow this simple check-list:

1. Download the trunk of the correct project
2. Add your code, change any existing files as needed
3. Commit in your local branch
4. Push to launchpad (to the public copy of your branch)
5. Propose a merge request
