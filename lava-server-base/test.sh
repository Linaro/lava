#!/bin/sh

set -e

echo "Install git"
apt-get install --no-install-recommends --yes git
echo "done"
echo

echo "Clone lava.git"
cd /root/
git clone https://git.lavasoftware.org/lava/lava.git
cd lava/
echo "done"
echo

echo "Check stretch dependencies"
PACKAGES=$(./share/requires.py -p lava-server -d debian -s stretch -n)
for pkg in $PACKAGES
do
  echo "* $pkg"
  dpkg -l "$pkg" > /dev/null
done
echo "Check stretch-backports dependencies"
PACKAGES=$(./share/requires.py -p lava-server -d debian -s stretch-backports -n)
for pkg in $PACKAGES
do
  echo "* $pkg"
  dpkg-query --show --showformat '${Version}\n' "$pkg" | grep -q bpo
done
