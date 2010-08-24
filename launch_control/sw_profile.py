"""
Helper module with SoftwarePackage and SoftwareProfile classes.
"""
from __future__ import with_statement
import apt
try:
    from debian.debian_support import version_compare as debian_version_compare
except ImportError:
    from debian_bundle.debian_support import version_compare as debian_version_compare


class SoftwareProfileError(StandardError):
    """
    Exception raised when something goes wrong inside this module and no
    standard exception class is ready to support it.
    """


class SoftwarePackage(object):
    """
    Software package class.
    Immutable glorified tuple with 'name', 'version' fields.

    Instances can be used as hash key.
    >>> d = {}
    >>> d[SoftwarePackage('foo', '1.0')] = True
    >>> d[SoftwarePackage('foo', '1.0')]
    True

    Instances support comparison:
    >>> pkg1 = SoftwarePackage('launch-control', '1.0.0')
    >>> pkg2 = SoftwarePackage('launch-control', '1.0.0')
    >>> pkg1 == pkg2
    True

    Instances support ordering.
    Ordering depends on package name and version. Package name takes
    precedence.
    >>> pkg1 = SoftwarePackage('a', '1.0.1')
    >>> pkg2 = SoftwarePackage('b', '1.0.0')
    >>> pkg1 < pkg2
    True
    >>> pkg1 > pkg2
    False
    >>> pkg1 == pkg2
    False

    With identical package names package version determines order
    Versions are compared using debian version comparison algorithms.
    >>> pkg1 = SoftwarePackage('launch-control', '1.0.0')
    >>> pkg2 = SoftwarePackage('launch-control', '1.0.1')
    >>> pkg1 < pkg2
    True
    >>> pkg1 > pkg2
    False
    >>> pkg1 == pkg2
    False

    There is also some support for pretty printing:
    >>> SoftwarePackage('foobar', '1.alpha1')
    <SoftwarePackage foobar 1.alpha1>
    """
    def __init__(self, name, version):
        """
        Initialize package with name and version
        """
        self._name = name
        self._version = version

    @property
    def name(self):
        """
        Read-only name property
        """
        return self._name

    @property
    def version(self):
        """
        Read-only version property
        """
        return self._version

    def __repr__(self):
        return '<SoftwarePackage %s %s>' % (self.name, self.version)

    def __hash__(self):
        return hash((self.name, self.version))

    def __cmp__(self, other):
        result = cmp(self.name, other.name)
        if result != 0:
            return result
        return debian_version_compare(self.version, other.version)


class SoftwareProfile(object):
    """
    Software profile class.

    Stores what we consider to be the 'software profile' of a test
    execution environment. The profile is composed of two bits of
    information:
        * List of all installed software packages
        * Identity of the software image or installer that was used to
          create this system
    """
    def __init__(self):
        self.packages = []
        self.image_id = None

    def inspect_system(self):
        """
        Inspect current system and discover installed packages and image
        id.
        """
        self.packages = self.find_installed_packages()
        self.image_id = self.find_image_id()

    # FIXME: restore this to being a class method
    # once mocker classmethod support bug is fixed
    # @classmethod
    def find_installed_packages(cls):
        """
        Find installed software packages.
        Interrogates apt cache to find all installed packages.
        """
        # FIXME: which exceptions might apt throw?
        apt_cache = apt.Cache()
        packages = []
        for apt_pkg in apt_cache:
            if apt_pkg.is_installed:
                pkg = SoftwarePackage(apt_pkg.name, apt_pkg.installed.version)
                packages.append(pkg)
        return packages

    # FIXME: restore this to being a class method
    # once mocker classmethod support bug is fixed
    # @classmethod
    def _parse_lsb_release(cls, stream):
        """
        Parse a stream containing /etc/lsb-release.
        The `stream' can be a real file() or any file-like object with
        support for iteration over lines.

        The code looks over key=value lines looking for DISTRIB_DESCRIPTION.
        >>> SoftwareProfile()._parse_lsb_release(
        ...     "DISTRIB_DESCRIPTION=foobar".splitlines())
        'foobar'

        If it cannot be found (which should not happen) a SoftwareProfileError
        is raised.
        >>> SoftwareProfile()._parse_lsb_release([])
        Traceback (most recent call last):
            ...
        SoftwareProfileError: Unable to find system image identity

        Lines that are not key=value will raise ValueError.
        >>> SoftwareProfile()._parse_lsb_release(
        ...     "foobar".splitlines())
        Traceback (most recent call last):
            ...
        ValueError: need more than 1 value to unpack
        """

        for line in stream:
            key, value = line.split('=', 1)
            if key.strip() == 'DISTRIB_DESCRIPTION':
                return value.strip()
        else:
            raise SoftwareProfileError("Unable to find system image identity")

    # FIXME: restore this to being a class method
    # once mocker classmethod support bug is fixed
    # @classmethod
    def find_image_id(cls):
        """
        Find system image identity.

        Inspects /etc/lsb-release for DISTRIB_DESCRIPTION field.
        See _parse_lsb_release() for details.
        """
        # FIXME: work with lex-builder to make additional, better,
        # information available. Something that is not lost on system
        # upgrades
        with open('/etc/lsb-release', 'rt') as stream:
            return cls._parse_lsb_release(stream)
