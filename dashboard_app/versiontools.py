import os


class Version(object):

    def __init__(self, major, minor, micro=0, releaselevel="dev", serial=0):
        assert releaselevel in ('dev', 'alpha', 'beta', 'candidate', 'final')
        self.major = major
        self.minor = minor
        self.micro = micro
        self.releaselevel = releaselevel
        self.serial = serial

        origin = os.path.dirname(os.path.abspath(__file__))
        self._post_init_fixup(origin)

    @property
    def as_tuple(self):
        return (self.major, self.minor, self.micro, self.releaselevel, self.serial)

    def _post_init_fixup(self, origin):
        if self.releaselevel == "dev" and not self.serial:
            self.serial = self._get_revision_from_bzr(origin)

    def __repr__(self):
        return 'Version(%r, %r, %r, %r, %r)' % (
            self.major, self.minor, self.micro, self.releaselevel,
            self.serial)

    def __str__(self):
        """
        Return a string representing the version of this package
        """
        version = "%s.%s" % (self.major, self.minor)
        if self.micro != 0:
            version += ".%s" % self.micro
        if self.releaselevel != 'final':
            version += ".%s" % self.releaselevel
        if self.releaselevel == 'dev' and self.serial:
            version += '.%s' % self.serial
        return version

    def _get_revision_from_bzr(self, origin):
        import bzrlib
        with bzrlib.initialize():
            from bzrlib.branch import Branch
            branch = Branch.open_containing(origin)[0]
            return branch.last_revision_info()[0]
