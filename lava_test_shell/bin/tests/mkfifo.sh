success_color=""
failure_color=""
end_color=""
if [ -t 1 ]; then
  success_color="\033[0;32;40m"
  failure_color="\033[0;31;40m"
  end_color="\033[m"
fi

fails=0
runtest() {
  expected_outcome="$1"
  shift
  testname="$1"
  shift
  if $@; then
    outcome=succeeds
  else
    outcome=fails
  fi
  if [ "$outcome" = "$expected_outcome" ]; then
    printf "$success_color$testname=pass$end_color\n"
  else
    printf "$failure_color$testname=fail$end_color\n" 
    fails=$(($fails + 1))
  fi
}

succeeds() {
  runtest succeeds $@
}
fails() {
  runtest fails $@
}

./mkfifo testfifo1
succeeds createfifo [ -p testfifo1 ]

fails usage ./mkfifo

touch testfifo_not_really
fails no_permission ./mkfifo testfifo_not_really

rm -rf testfifo*
exit $fails
