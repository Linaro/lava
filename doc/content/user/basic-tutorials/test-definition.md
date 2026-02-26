# Test definitions

The test definition is a `yaml` file that describe the tests that you want LAVA
to run on the DUT.

## Smoke example

Let's look at this example:

```yaml
--8<-- "tests/smoke.yaml"
```

## Metadata

The `metadata` dictionary describes the test. `format` and `name` are mandatory
while `description` is optional.

## Run

The dictionary list the actions that LAVA should execute on the DUT. The only
available key is `steps`.

`steps` is an array that will be transformed into a shell script that LAVA will
run on the DUT.

In this example, `run.steps` will be rendered into the following shell script:

```shell
--8<-- "tests/smoke.sh"
```

### LAVA test helpers

The LAVA Test Helpers are scripts maintained in the LAVA codebase, like
`lava-test-case`. These are designed to work using only the barest
minimum of operating system support, to make them portable to all deployments.
The helpers are mainly used to:

* embed information from LAVA into the test shell
* support communication with LAVA during test runs

#### lava-test-case

##### Result

Record a test result using the `--result` argument:

```shell
lava-test-case <test-case-id> --result <pass|fail|skip|unknown> [--measurement <val>] [--units <unit>] [--output <file>]
```

##### Shell

Record a test result using the `--shell` command exit code:

```shell
lava-test-case <test-case-id> --shell <command>
```

If `<command>` exits with 0, the result is `pass`. Otherwise, it is `fail`.

!!! warning
    When using `--shell`, multiple commands or combined on-liner command with pipes
    and redirects should be quoted so it is passed as a single argument and the final
    exit code is checked.
    ```yaml title="Correct"
    - lava-test-case check-os --shell "cat /etc/os-release | grep 'ID=debian'"
    ```
    If not quoted, only the exit code of the first command is checked and a
    `| grep <pattern>` check could potentially prevent the helper from sending
    the LAVA test result signal and lead to missing test result.
    ```yaml title="Incorrect"
    - lava-test-case check-os --shell cat /etc/os-release | grep "ID=debian"
    ```

##### Output

Attach output from a file to a test result using `--output`:

```shell
lava-test-case <test-case-id> --result <result> --output <file>
```

This streams the contents of `<file>` between start/end test case signals,
similar to how `--shell` captures command output. Useful when the test output
has already been saved to a file by a previous step.

#### lava-test-set

Group test cases into named sets. This allows test writers to subdivide
results within a single test definition using an arbitrary label:

```shell
lava-test-set start <name>
lava-test-set stop
```

```yaml
steps:
  - lava-test-set start network-tests
  - lava-test-case ping --shell ping -c4 localhost
  - lava-test-set stop
```

#### lava-test-reference

Some test cases may relate to specific bug reports or have specific URLs
associated with the result. This help can be used to associate a URL with a
test result:

```shell
lava-test-reference <test-case-id> --result <result> --reference <url>
```

!!! note
    The URL should be a simple file reference, complex query strings could
    fail to be parsed.

#### lava-test-raise

Raise a `TestError` to abort the current test job immediately:

```shell
lava-test-raise <message>
```

This is useful when a setup step fails and running subsequent tests would be
pointless. The message is included in the error reported by LAVA.

#### lava-background-process-

Manage background processes during the test:

```yaml
steps:
  - lava-background-process-start MON --cmd "top -b"
  - ./run-my-tests.sh
  - lava-background-process-stop MON
```

### Device Information Helpers

Some elements of the static device configuration are exposed to the test shell,
where it is safe to do so and where the admin has explicitly configured the
information.

#### lava-target-ip

Prints the target's IP address if configured by the admin in device dictionary
using [device_ip](../../technical-references/configuration/device-dictionary.md#device_ip).
Devices with a fixed IPv4 address configured in the device dictionary will populate
this field. Test writers can use this in an Docker container to connect to the device:

```shell
ping -c4 $(lava-target-ip)
```

#### lava-target-mac

Prints the target's MAC address if configured by the admin in device dictionary
using [device_mac](../../technical-references/configuration/device-dictionary.md#device_mac).
This can be useful to look up the IP address of the device:

```shell
echo $(lava-target-mac)
```

#### lava-echo-ipv4

Prints the IPv4 address for a given network interface using `ifconfig` or `ip`:

```shell
lava-echo-ipv4 <interface>
```

#### lava-target-storage

Prints available storage devices if configured by the admin in device dictionary
using [storage_info](../../technical-references/configuration/device-dictionary.md#storage_info).

Without arguments, outputs one line per device with the name and value separated
by a tab:

```shell
$ lava-target-storage
UMS	/dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0xac2400d300000054-0:0
SATA	/dev/disk/by-id/ata-ST500DM002-1BD142_W3T79GCW
```

With a name filter, outputs only the matching device value:

```shell
$ lava-target-storage UMS
/dev/disk/by-id/usb-Linux_UMS_disk_0_WaRP7-0xac2400d300000054-0:0
```

If there is no matching name, exits non-zero and outputs nothing.

### Using custom scripts

When multiple steps are necessary to run a test and get usable output, write a
custom script to go alongside the YAML and execute it as a run step:

```yaml
run:
  steps:
    - ./my-script.sh arguments
```

You can choose whatever scripting language you prefer, as long as it is
available in the test image. The best practices are:

* Be verbose - Add progress messages, error handling, and debug output so
  that test logs are useful during triage. Control the total amount of output
  to keep logs readable.
* Watch out for `cd` - If you change directories inside a script, save the
original working directory first and return to it at the end.
* Wait for subprocesses - In Python, use `subprocess.check_call()` or
`subprocess.run()` instead of `subprocess.Popen()` when calling LAVA helpers.
`Popen` returns immediately, which can cause output to arrive after the test
definition finishes and lead to missing results.
* Make it portable - Scripts should check if the LAVA helper in `$PATH` to
determine whether they are running inside LAVA. When the helper is not available,
report results with `echo` or `print()` instead. This allows the same script to
run both inside and outside of LAVA, helping developers reproduce issues without
the full CI system.

    ```shell
    #!/bin/sh
    if command -v lava-test-case >/dev/null 2>&1; then
        lava-test-case my-test --result pass
    else
        echo "my-test: pass"
    fi
    ```

See also [test writing guidelines](https://github.com/Linaro/test-definitions/blob/master/docs/test-writing-guidelines.md#test-writing-guidelines), typically the **Running in
LAVA** section. For test definition examples that follow the best practices,
see [automated](https://github.com/Linaro/test-definitions/tree/master/automated).

## Install

Before running the run steps, LAVA can also `install` some Git repositories and
run arbitrary shell commands to prepare for the following test runs.

### git-repos

Specifies the Git repositories to be cloned into the test working directory.
The repositories are cloned on the LAVA worker and applied to the test image as
part of the LAVA overlay.

```yaml
install:
  git-repos:
    - url: https://gitlab.com/lava/lava.git
      branch: 2026.01
      destination: lava202601
```

### steps

Specifies arbitrary shell commands to run during the install phase. The install
steps are run directly on the DUT.

```yaml
install:
  git-repos:
    - url: https://example.com/repo.git
  steps:
    - cd repo
    - make install
```

## Expected

The `expected` dictionary allows users to define a list of expected test cases.
At the end of each test run, missing expected test cases from the test results
are marked as fail. Conversely, test cases present in the results but not in the
expected list are logged as warnings.

With the following test definition example, tc3 and tc4 will be reported as `fail`,
and warnings will be logged for tc5 and tc6.

```yaml title="Test definition"
metadata:
  format: Lava-Test Test Definition 1.0
  name: expected-testdef-example
run:
  steps: []
expected:
  - tc1
  - tc2
  - tc3
  - tc4
```

The list can be defined in either the test definition or the job definition. If
both are provided, the value in the job definition takes precedence.

!!!warning "Limitation"
    Expected test cases defined in test definition from `git` are checked and
    reported after test execution. If the test definition not get executed at
    all, they are not reported. The limitation exists because these test
    definitions and the expected test case lists defined inside may be
    unreachable or not deployed yet when job exists on error. If you need
    consistent and predictable job results for the test suites and cases, you
    should provide the expected test cases in the
    [job definition](../../technical-references/job-definition/actions/test.md#expected).

--8<-- "refs.txt"
