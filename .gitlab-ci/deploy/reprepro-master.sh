#!/bin/sh

set -e
set -x

if [ "$1" = "setup" ]
then
    true
else
    LAVA_BUILDD=`pwd`
    DAILY="daily"
    R_OPT="--ignore=wrongdistribution"
    BASEDIR="${HOME}/repository/${DAILY}"

    ls -l ${LAVA_BUILDD}/build/
    find ${LAVA_BUILDD}/build/ -type f -name 'lava_*.changes'

    echo "Checking if the build has already been deployed."
    if [ -f ${BASEDIR}/latest ]; then
        LATEST=`cat ${BASEDIR}/latest`
        CHANGES=`find ${LAVA_BUILDD}/build/ -type f -name 'lava_*buster_amd64.changes'`
        VERSION=`grep Version ${CHANGES} | cut -d' ' -f2`
        DPKG=`dpkg --compare-versions ${VERSION} le ${LATEST} ; echo $?` || true
        if [ "${DPKG}" = "0" ]; then
            echo "Nothing to do - ${LATEST} is newer than or equal to ${VERSION}."
            dcmd rm ${LAVA_BUILDD}/build/lava_*.changes
            exit 0
        fi
    fi

    echo "Updating ${BASEDIR}"
    echo "reprepro-master.sh daily update running in " ${LAVA_BUILDD}
    if [ -d "${BASEDIR}/dists/stretch-backports" ]; then
        reprepro -b ${BASEDIR} ${R_OPT} include stretch-backports ${LAVA_BUILDD}/build/lava_*stretch_amd64.changes
        dcmd rm ${LAVA_BUILDD}/build/lava_*stretch_amd64.changes

        # enable if stretch_arm64 is enabled.
        # reprepro -b ${BASEDIR} ${R_OPT} include stretch-backports ${LAVA_BUILDD}/build/lava_*stretch_arm64.changes
        # dcmd rm ${LAVA_BUILDD}/build/lava_*stretch_arm64.changes

        reprepro -b ${BASEDIR} list stretch-backports
    fi
    if [ -d "${BASEDIR}/dists/buster" ]; then
        reprepro -b ${BASEDIR} include buster ${LAVA_BUILDD}/build/lava_*buster_amd64.changes
        CHANGES=`find ${LAVA_BUILDD}/build/ -type f -name 'lava_*buster_amd64.changes'`
        VERSION=`grep Version ${CHANGES} | cut -d' ' -f2`
        dcmd rm ${LAVA_BUILDD}/build/lava_*buster_amd64.changes

        # restore once ready to be merged.
        # reprepro -b ${BASEDIR} include buster ${LAVA_BUILDD}/build/lava_*buster_arm64.changes
        # dcmd rm ${LAVA_BUILDD}/build/lava_*buster_arm64.changes

        reprepro -b ${BASEDIR} list buster
        echo "Updating latest"
        echo ${VERSION} > ${BASEDIR}/latest
    fi

fi
