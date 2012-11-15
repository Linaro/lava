# Sigh.

import os
import pkg_resources

from zc.buildout.easy_install import _final_version, realpath, Installer

def _obtain(self, requirement, source=None):
    # initialize out index for this project:
    index = self._index

    if index.obtain(requirement) is None:
        # Nothing is available.
        return None

    # Filter the available dists for the requirement and source flag.  If
    # we are not supposed to include site-packages for the given egg, we
    # also filter those out. Even if include_site_packages is False and so
    # we have excluded site packages from the _env's paths (see
    # Installer.__init__), we need to do the filtering here because an
    # .egg-link, such as one for setuptools or zc.buildout installed by
    # zc.buildout.buildout.Buildout.bootstrap, can indirectly include a
    # path in our _site_packages.
    dists = [dist for dist in index[requirement.project_name] if (
                dist in requirement and (
                    dist.location not in self._site_packages or
                    self.allow_site_package_egg(dist.project_name))
                and (
                    (not source) or
                    (dist.precedence == pkg_resources.SOURCE_DIST))
                )
             ]

    # If we prefer final dists, filter for final and use the
    # result if it is non empty.
    if self._prefer_final:
        fdists = [dist for dist in dists
                  if _final_version(dist.parsed_version)
                  ]
        if fdists:
            # There are final dists, so only use those
            dists = fdists

    # Now find the best one:
    best = []
    bestv = ()
    for dist in dists:
        distv = dist.parsed_version
        if distv > bestv:
            best = [dist]
            bestv = distv
        elif distv == bestv:
            best.append(dist)

    if not best:
        return None

    if len(best) == 1:
        return best[0]

    if self._download_cache:
        for dist in best:
            if (realpath(os.path.dirname(dist.location))
                ==
                self._download_cache
                ):
                return dist

    for dist in best:
        if dist.location.startswith('http://pypi.python.org/'):
            return dist

    best.sort()
    return best[-1]

Installer._obtain = _obtain

from zc.recipe.egg import Scripts
