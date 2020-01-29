#!/bin/sh

set -e
set -x

if [ "$1" = "setup" ]
then
    true
else
    LAVA_BUILDD=`pwd`

    R_OPT="--ignore=wrongdistribution"
    BASEDIR="${HOME}/repository/current-release"
    # location of snapshot directory
    SNAPSHOT="${HOME}/repository/snapshot/"

    ls -l ${LAVA_BUILDD}/_build/
    find ${LAVA_BUILDD}/_build/ -type f -name 'lava_*.changes'

    echo "Checking if the build has already been deployed."
    if [ -f ${BASEDIR}/latest ]; then
        LATEST=`cat ${BASEDIR}/latest`
        CHANGES=`find ${LAVA_BUILDD}/_build/ -type f -name 'lava_*buster_amd64.changes'`
        VERSION=`grep Version ${CHANGES} | cut -d' ' -f2`
        DPKG=`dpkg --compare-versions ${VERSION} le ${LATEST} ; echo $?` || true
        if [ "${DPKG}" = "0" ]; then
            echo "Nothing to do - ${LATEST} is newer than or equal to ${VERSION}."
            dcmd rm ${LAVA_BUILDD}/_build/lava_*.changes
            exit 0
        fi
    fi

    YEAR=`date +%Y`
    MONTH=`date +%m`
    DAY=`date +%d`

    # Copy current repo to old-release, and update the release symlink
    # to point there atomically
    cd ${HOME}/repository
    cp -a current-release old-release
    ln -snfv old-release release

    # Now work in the (not linked) current-release directory, leaving
    # the existing working config in old-release
    echo "Updating ${BASEDIR}"
    echo "reprepro-master.sh release update running in " ${LAVA_BUILDD}
    if [ -d "${BASEDIR}/dists/buster" ]; then
        reprepro -b ${BASEDIR} include buster ${LAVA_BUILDD}/_build/lava_*buster_amd64.changes
        CHANGES=`find ${LAVA_BUILDD}/_build/ -type f -name 'lava_*buster_amd64.changes'`
        VERSION=`grep Version ${CHANGES} | cut -d' ' -f2`
        mkdir -p ${SNAPSHOT}/buster/${YEAR}/${MONTH}/${DAY}/
        dcmd cp ${LAVA_BUILDD}/_build/lava_*buster_*.changes ${SNAPSHOT}/buster/${YEAR}/${MONTH}/${DAY}/
        dcmd rm ${LAVA_BUILDD}/_build/lava_*buster_amd64.changes

        reprepro -b ${BASEDIR} list buster
        echo "Updating latest"
        echo ${VERSION} > ${BASEDIR}/latest
    fi

    # Assuming this all worked, the release manager will now check and
    # sign the final Release files that reprepro created, then
    # ln -snf current-release release
    # rm -rf old-release

fi
