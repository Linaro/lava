#!/bin/sh

set -e
set -x

if [ "$1" = "setup" ]
then
    true
else
    LAVA_BUILDD=`pwd`
    RELEASE="notreleased"
    R_OPT="--ignore=wrongdistribution"
    BASEDIR="${HOME}/repository/${RELEASE}"
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

    echo "Updating ${BASEDIR}"
    echo "reprepro-master.sh release update running in " ${LAVA_BUILDD}
    if [ -d "${BASEDIR}/dists/stretch-backports" ]; then
        reprepro -b ${BASEDIR} ${R_OPT} include stretch-backports ${LAVA_BUILDD}/_build/lava_*stretch_amd64.changes
        mkdir -p ${SNAPSHOT}/stretch/${YEAR}/${MONTH}/${DAY}/
        dcmd cp ${LAVA_BUILDD}/_build/lava_*stretch_*.changes ${SNAPSHOT}/stretch/${YEAR}/${MONTH}/${DAY}/
        dcmd rm ${LAVA_BUILDD}/_build/lava_*stretch_amd64.changes

        reprepro -b ${BASEDIR} ${R_OPT} include stretch-backports ${LAVA_BUILDD}/_build/lava_*stretch_arm64.changes
        dcmd rm ${LAVA_BUILDD}/_build/lava_*stretch_arm64.changes

        reprepro -b ${BASEDIR} list stretch-backports
    fi
    if [ -d "${BASEDIR}/dists/buster" ]; then
        reprepro -b ${BASEDIR} include buster ${LAVA_BUILDD}/_build/lava_*buster_amd64.changes
        CHANGES=`find ${LAVA_BUILDD}/_build/ -type f -name 'lava_*buster_amd64.changes'`
        VERSION=`grep Version ${CHANGES} | cut -d' ' -f2`
        mkdir -p ${SNAPSHOT}/buster/${YEAR}/${MONTH}/${DAY}/
        dcmd cp ${LAVA_BUILDD}/_build/lava_*buster_*.changes ${SNAPSHOT}/buster/${YEAR}/${MONTH}/${DAY}/
        dcmd rm ${LAVA_BUILDD}/_build/lava_*buster_amd64.changes

        reprepro -b ${BASEDIR} include buster ${LAVA_BUILDD}/_build/lava_*buster_arm64.changes
        dcmd rm ${LAVA_BUILDD}/_build/lava_*buster_arm64.changes

        reprepro -b ${BASEDIR} list buster
        echo "Updating latest"
        echo ${VERSION} > ${BASEDIR}/latest
    fi

fi
