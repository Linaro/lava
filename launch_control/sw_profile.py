"""
Helper module with SoftwarePackage and SoftwareProfile classes.
"""

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
    Ordering depends on package name:
    >>> pkg1 = SoftwarePackage('a', '1.0.1')
    >>> pkg2 = SoftwarePackage('b', '1.0.0')
    >>> pkg1 < pkg2
    True
    >>> pkg1 > pkg2
    False
    >>> pkg1 == pkg2
    False

    With identical package names package version determines order:
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

    def __eq__(self, other):
        return self.name == other.name and self.version == other.version

    def __lt__(self, other):
        return self.name < other.name or (
                self.name == other.name
                and self.version < other.version)


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
    def find_installed_packages(cls, apt_cache=None):
        """
        Find installed software packages.

        Interrogates apt cache to find all installed packages
        Raises SystemError if apt or apt cache is not available.

        An existing instance of apt_cache may be passed, this will
        prevent this function from opening another cache. This can also
        be used for testing.

        Let's setup a simple fake apt cache and see how it works.
        First let's make two fake apt packages. We'll use mocker
        module to do this:
        >>> from thirdparty.mocker import Mocker

        Let's make a object that mocks installed package:
        >>> mocker1 = Mocker()
        >>> pkg1 = mocker1.mock()

        Package pkg1 has a name property that returns 'foo'
        >>> pkg1.name # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker1.result('foo')

        An is_installed property that returns True
        >>> pkg1.is_installed # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker1.result(True)

        And a installed.version property that returns '1.0'
        >>> pkg1.installed.version # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker1.result('1.0')
        >>> mocker1.replay()

        And another object that mocks an uninstalled package. Note that
        we don't even mock the name as it will never be acessed.
        >>> mocker2 = Mocker()
        >>> pkg2 = mocker2.mock()
        >>> pkg2.is_installed # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker2.result(False)
        >>> mocker2.replay()

        Finally let's mock the apt cache
        >>> mocker3 = Mocker()
        >>> apt_cache = mocker3.mock()

        We need to mock the iteration over all packages that returns an
        iterator over our packages.
        >>> iter(apt_cache) # doctest:+ELLIPSIS
        <listiterator object at 0x...>
        >>> mocker3.result(iter([pkg1, pkg2]))
        >>> mocker3.replay()

        Now we're ready to call find_installed_packages() now.
        Observe that only pkg1 is listed because pkg2 was not installed.
        >>> SoftwareProfile().find_installed_packages(apt_cache=apt_cache)
        [<SoftwarePackage foo 1.0>]

        We can verify that all mocked properties and methods were
        called.
        >>> mocker1.verify()
        >>> mocker2.verify()
        >>> mocker3.verify()
        """
        if apt_cache is None:
            try:
                import apt
            except ImportError:
                raise SoftwareProfileError("Unable to access apt")
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

        Let's test this function with some mock objects:
        >>> from thirdparty.mocker import Mocker, ANY

        First we'll make a fake stream-like object. It needs to support
        __enter__() and __exit__ since it's used inside a with
        statement.
        >>> mocker1 = Mocker()
        >>> fake_file = mocker1.mock()
        >>> fake_file.__enter__() # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> fake_file.__exit__(ANY, ANY, ANY) # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker1.replay()

        Now let's replace the builtin open() function to return our fake
        file. Note we are only expected to open one specific file for
        reading. This is where we return our fake_file created above.
        >>> mocker2 = Mocker()
        >>> my_open = mocker2.replace("__builtin__.open")
        >>> my_open('/etc/lsb-release', 'rt') # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker2.result(fake_file)
        >>> mocker2.replay()

        Finally let's replace _parse_lsb_replease() since we don't want
        to test it here. It will simply return a dummy value. Doing it
        is a littler tricky, we'll patch an instance of
        SoftwareProfile() and replace _parse_lsb_release() with dummy
        method.
        >>> mocker3 = Mocker()
        >>> sw_profile_orig = SoftwareProfile()
        >>> sw_profile = mocker3.patch(sw_profile_orig)
        >>> sw_profile._parse_lsb_release(ANY) # doctest: +ELLIPSIS
        <thirdparty.mocker.Mock object at 0x...>
        >>> mocker3.result('foobar')
        >>> mocker3.replay()

        We are now ready for testing:
        >>> sw_profile_orig.find_image_id()
        'foobar'

        Let's restore everything to get open() back:
        >>> mocker1.restore()
        >>> mocker2.restore()
        >>> mocker3.restore()

        We can verify that our mock objects were used as planned:
        >>> mocker1.verify()
        >>> mocker2.verify()
        >>> mocker3.verify()
        """
        # FIXME: work with lex-builder to make additional, better,
        # information available. Something that is not lost on system
        # upgrades
        with open('/etc/lsb-release', 'rt') as stream:
            return cls._parse_lsb_release(stream)



def _test():
    """
    Test all docstrings.

    Usage: python sample.py [-v]
    """
    import doctest
    doctest.testmod()


if __name__ == "__main__":
    _test()
