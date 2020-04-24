###default parameters from test definition###
######
###test parameters from job submission###
######
set -e
set -x
export TESTRUN_ID=0_smoke-tests-basic
cd /lava-4212/0/tests/0_smoke-tests-basic
UUID=`cat uuid`
set +x
echo "<LAVA_SIGNAL_STARTRUN $TESTRUN_ID $UUID>"
set -x
lava-test-case linux-posix-pwd --shell pwd
lava-test-case linux-posix-uname --shell uname -a
lava-test-case linux-posix-vmstat --shell vmstat
lava-test-case linux-posix-ifconfig --shell ifconfig -a
lava-test-case linux-posix-lscpu --shell lscpu
lava-test-case linux-posix-lsb_release --shell lsb_release -a
set +x
echo "<LAVA_SIGNAL_ENDRUN $TESTRUN_ID $UUID>"
