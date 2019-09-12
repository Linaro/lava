#!/bin/sh

set -e

echo "Clone lava.git"
git clone https://git.lavasoftware.org/lava/lava.git /root/lava
echo "done"
echo

echo "Check buster dependencies"
PACKAGES=$(/root/lava/share/requires.py -p lava-dispatcher -d debian -s buster -n| sed "s# #\n#g" | sort -u | xargs echo)
for pkg in $PACKAGES
do
  echo "* $pkg"
  VERSION=$(dpkg-query --show --showformat '${Version}\n' "$pkg")
  echo "  => $VERSION"
  # Test that the package exist and it's not from buster-backports
  dpkg-query --show --showformat '${Version}\n' "$pkg" | grep -qv bpo
done
