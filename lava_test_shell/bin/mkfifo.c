#include <sys/types.h>
#include <sys/stat.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>

int main(int argc, char** argv) {
  if (argc != 2) {
    printf("usage: %s FILE\n", argv[0]);
    return EINVAL;
  }
  int ret = mkfifo(argv[1], 0666);
  if (ret == 0) {
    return ret;
  } else {
    ret = errno;
    printf("%s: %s\n", argv[0], strerror(ret));
    return ret;
  }
}
