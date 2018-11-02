#!/bin/sh

set -e

echo "Install git"
apt-get install --no-install-recommends --yes git
echo "done"
echo

echo "Clone lava.git"
git clone https://git.lavasoftware.org/lava/lava.git /root/lava
echo "done"
echo

echo "Check stretch dependencies"
PACKAGES=$(/root/lava/share/requires.py -p lava-server -d debian -s stretch -n| sed "s# #\n#g" | sort -u | xargs echo)
for pkg in $PACKAGES
do
  echo "* $pkg"
  VERSION=$(dpkg-query --show --showformat '${Version}\n' "$pkg")
  echo "  => $VERSION"
  # Test that the package exist and it's not from stretch-backports
  dpkg-query --show --showformat '${Version}\n' "$pkg" | grep -qv bpo
done

echo "Check stretch-backports dependencies"
PACKAGES=$(/root/lava/share/requires.py -p lava-server -d debian -s stretch-backports -n| sed "s# #\n#g" | sort -u | xargs echo)
for pkg in $PACKAGES
do
  echo "* $pkg"
  VERSION=$(dpkg-query --show --showformat '${Version}\n' "$pkg")
  echo "  => $VERSION"
  dpkg-query --show --showformat '${Version}\n' "$pkg" | grep -q bpo
done
