"""
Helper module with software profile class
"""
import apt


class SoftwarePackage(object):
    """
    Software package class.

    Immutable glorifled tuple with 'name', 'version' fields. Instances
    can be used as hash key.
    >>> d = {}
    >>> d[SoftwarePackage('foo', '1.0')] = True
    >>> d[SoftwarePackage('foo', '1.0')]
    True

    Instances support comparison:
    >>> pkg1 = SoftwarePackage('launch-control', '1.0.0')
    >>> pkg2 = SoftwarePackage('launch-control', '1.0.0')
    >>> pkg1 == pkg2
    True

    Ordering:
    >>> pkg1 = SoftwarePackage('launch-control', '1.0.0')
    >>> pkg2 = SoftwarePackage('launch-control', '1.0.1')
    >>> pkg1 < pkg2
    True
    >>> pkg1 > pkg2
    False
    >>> pkg1 == pkg2
    False

    And pretty-printing:
    >>> pkg1
    <SoftwarePackage launch-control 1.0.0>
    """
    __slots__ = ('_name', '_version')
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
    def __eq__(self, other):
        return self.name == other.name and self.version == other.version
    def __lt__(self, other):
        return self.name < other.name or (self.name == other.name and self.version < other.version)


class SoftwareProfile(object):
    """
    Software profile class.

    Stores what we consider to be the 'software profile' of a test execution environment.

    The profile is composed of two bits of information:
        * List of all installed software packages
        * Identity of the software image or installer that was used to
          create this system
    """
    def __init__(self):
        self._packages = []
        self._image_id = None
        self._inspect_system()
    @property
    def packages(self):
        """
        Iterator over all installed software packages
        """
        return iter(self._packages)
    @property
    def image_id(self):
        """
        Read-only property exposing image id
        """
        return self._image_id
    def _inspect_system(self):
        self._find_installed_packages()
        self._find_image_id()
    def _find_installed_packages(self):
        """
        Find installed software packages.

        Interrogates apt cache to find all installed packages
        Raises SystemError if apt or apt cache is not available
        """
        try:
            import apt
        except ImportError:
            raise SystemError("Unable to access apt")
        # FIXME: which exceptions might apt throw?
        cache = apt.Cache()
        for apt_pkg in cache:
            if apt_pkg.is_installed:
                pkg = SoftwarePackage(apt_pkg.name, apt_pkg.installed.version)
                self._packages.append(pkg)
    def _find_image_id(self):
        """
        Find system image identity.

        Inspects /etc/lsb-release for DISTRIB_DESCRIPTION field.
        Raises SystemError if this key is not available
        """
        # FIXME: work with lex-builder to make additional, better,
        # information available. Something that is not lost on system
        # upgrades
        with open('/etc/lsb-release', 'rt') as stream:
            for line in stream:
                key, value = line.split('=', 1)
                if key.strip() == 'DISTRIB_DESCRIPTION':
                    self._image_id = value.strip()
                    break
            else:
                raise SystemError("Unable to find system image identity")



def _test():
    """
    Test all docstrings.

    Usage: python sample.py [-v]
    """
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    _test()
