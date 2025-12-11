# Test Actions

The test action executes tests on the DUT after booting. It collects output,
parses results, and reports test outcomes.

**Key rules for using test actions:**

* A test action **never** boots the device - a [boot action](boot.md) **must**
  be defined before it.

* LAVA support scripts are prepared by the [deploy action](deploy/index.md) and
  remain available for all test definitions until the next deploy block.

* Multiple test definitions can be listed within the same test block to run
  sequentially without rebooting the device.

There are 4 types of test actions:

* [**Lava-test-shell definitions**](#definitions) (YAML directive: `definitions`)
  are used for POSIX compliant operating systems on the DUT. The deployed system
  is expected to support a POSIX shell environment (`/bin/ash`, `/bin/dash` or
  `/bin/bash` are the most common) so that LAVA can execute the LAVA Test Shell
  Helper scripts.

* [**Output monitors**](#monitors) (YAML directive: `monitors`) are used for
  devices which have no POSIX shell and start the test (and corresponding output)
  immediately after booting, for example microcontroller/IoT boards.

* [**Interactive tests**](#interactive) (YAML directive: `interactive`) are
  further extension of `monitor` tests idea, allowing not just matching some
  output from a device, but also feeding some input. They are useful for
  non-POSIX shells like bootloaders (u-boot for instance) and other interactive
  command-line applications.

* [**Test services**](#services) (YAML directive: services) are used for
  starting docker-compose based containers on the LAVA worker. It enables
  running custom services for the needs in test definitions.

## Definitions

```yaml title="Lava-test-shell definitions"
- test:
    timeout:
      minutes: 5
    definitions:
    - name: smoke-tests
      from: git
      repository: https://github.com/Linaro/test-definitions
      path: automated/linux/smoke/smoke.yaml
    - name: smoke-tests-net
      from: git
      repository: https://gitlab.com/lava/functional-tests.git
      path: posix/smoke-tests-net.yaml
```

### name

The unique test suite name to use. It replaces the name from the YAML.

### repository

A publicly readable repository location.

### from

The type of the repository is **not** guessed, it **must** be specified
explicitly. Support is available for [git](#git), [url](#url) and [inline](#inline).

#### git

A remote git repository which needs to be cloned by the LAVA worker.

Optional parameters:

* revision (`str`, default: `null`): specific commit SHA to check out
* branch (`str`, default: `null`): git branch to clone
* shallow (`bool`, default: `true`): perform a shallow git clone
* history (`bool`, default: `false`): include full git history
* recursive (`bool`, default: `false`): clone submodules recursively

#### url

```yaml title="Test definition from url" hl_lines="4-5"
- test:
    definitions:
    - name: smoke-tests
      from: url
      repository: https://github.com/Linaro/test-definitions/releases/download/2025.10.01/2025.10.tar.zst
      compression: zstd
      path: automated/linux/smoke/smoke.yaml
```

The repository must be a tar archive containing the test definitions.

`compression` is an optional string for providing decompression method to apply
before extracting. Supported: `bz2`, `gz`, `xz` and `zstd`.

#### inline

A simple test definition present in the same file as the job submission,
instead of from a separate file or VCS repository. This allows tests to be run
based on a single file. When combined with `file://` URLs to the `deploy`
parameters, this allows tests to run without needing external access.

```yaml title="Test definition from inline" hl_lines="4-14"
- test:
    definitions:
    - name: health-checks
      from: inline
      path: inline/health-checks.yaml
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: health checks
        run:
          steps:
            - lava-test-case check-version --shell cat /proc/version
            - lava-test-case lscpu --shell lscpu
            - lava-test-case lsblk --shell lsblk
```

For more details, see
[Using inline test definitions](/technical-references/test-definition/#using-inline-test-definitions)

### path

The path within that repository to the YAML file containing the test definition.

### parameters

(optional) Pass parameters to the Lava Test Shell Definition.

The key name can be `parameters` or `params`, both are supported.

The format is a YAML dictionary - the dictionary key is the name of the variable
to be made available to the test shell, the value is the value of that variable.

```yaml title="Test definition parameters" hl_lines="7-9"
- test:
    definitions:
    - name: smoke-test-lsblk
      from: git
      repository: https://github.com/Linaro/test-definitions
      path: automated/linux/smoke/smoke.yaml
      parameters:
        "SKIP_INSTALL": "true"
        "TESTS": "lsblk"
```

### expected

(optional) Provide an expected test case list. Missing test cases after test or
job run are reported as fails while extra cases are logged as warnings.

```yaml hl_lines="10-11"
- test:
  definitions:
    - name: smoke-test-lsblk
      from: git
      repository: https://github.com/Linaro/test-definitions
      path: automated/linux/smoke/smoke.yaml
      parameters:
        "SKIP_INSTALL": "true"
        "TESTS": "lsblk"
      expected:
        - lsblk
```

For test definitions from `inline`, the expected list must be defined at the job
level using the `expected` key, **not** inside the inline definition.

```yaml hl_lines="14-16"
  - test:
      definitions:
        - from: inline
          repository:
            metadata:
                format: Lava-Test Test Definition 1.0
                name: expected-tests
            run:
                steps:
                    - lava-test-case tc1 --result pass
                    - lava-test-case tc2 --result fail
          name: expected-tests
          path: inline/expected-tests.yaml
          expected:
            - tc1
            - tc2
```

!!!note "Always reported"
    Expected test cases defined in the job definition are always reported, even
    if the tests are not executed due to earlier job errors.

See also
[expected test cases in the test definition](../../../user/basic-tutorials/test-definition.md#expected).

### Additional support

#### Result checks

LAVA collects results from internal operations, these form the `lava` test
suite results as well as from the submitted test definitions. The full set of
results for a job are available at:

```sh
results/1234
```

LAVA records when a submitted test definition starts execution on the test
device. If the number of test definitions which started is not the same as the
number of test definitions submitted (allowing for the `lava` test suite
results), a warning will be displayed on this page.

#### TestSets

A TestSet is a group of lava test cases which will be collated within the LAVA
Results. This allows queries to look at a set of related test cases within a
single definition.

```yaml
- test:
   definitions:
   - repository:
       run:
         steps:
         - lava-test-set start first_set
         - lava-test-case date --shell ntpdate-debian
         - ls /
         - lava-test-case mount --shell mount
         - lava-test-set stop
         - lava-test-case uname --shell uname -a
```

This results in the `date` and `mount` test cases being included into a
`first_set` TestSet, independent of other test cases. The TestSet is
concluded with the `lava-test-set stop` command, meaning that the `uname`
test case has no test set, providing a structure like:

```yaml
results:
  first_set:
    date: pass
    mount: pass
  uname: pass
```

```python
{'results': {'first_set': {'date': 'pass', 'mount': 'pass'}, 'uname': 'pass'}}
```

Each TestSet name must be valid as a URL.

For test job `1234`, the `uname` test case would appear as:

```sh
results/1234/testset-def/uname
```

The `date` and `mount` test cases are referenced via the TestSet:

```sh
results/1234/testset-def/first_set/date
results/1234/testset-def/first_set/mount
```

A single test definition can start and stop different TestSets in sequence, as
long as the name of each TestSet is unique for that test definition.

For more details, see
[Test definitions](/technical-references/test-definition/)

## Monitors

Test jobs using Monitors **must**:

1. Execute automatically after boot.

2. Emit a unique `start` string before test runs.

3. Emit a unique `end` string after tests complete.

4. Provide a regex that captures test output and maps it to results without
   producing excessively long test case names.

### name

The name of the test suite.

### start

String or regex pattern that signals the beginning of test suite output.

If `start` does not match, the job will time out with no results.

### end

String or regex pattern that signals the end of test suite output.

If `end` does not match, the job will time out but the results of the current
boot will already have been reported.

!!! note
    `start` and `end` strings will match part of a line but make sure that each
    string is long enough that it can only match once per boot.

### pattern

Regex with named capture groups to extract test results from the test output.

For the following Zephyr test suite monitor:

```yaml
- test:
    monitors:
    - name: tests
      start: BOOTING ZEPHYR
      end: PROJECT EXECUTION SUCCESSFUL
      pattern: '(?P<test_case_id>\d+ *- [^-]+) (?P<measurement>\d+) tcs = [0-9]+ nsec'
      fixupdict:
        PASS: pass
        FAIL: fail
```

If the device output is of the form:

```text
***** BOOTING ZEPHYR OS v1.7.99 - BUILD: Apr 18 2018 10:00:55 *****
|-----------------------------------------------------------------------------|
|                            Latency Benchmark                                |
|-----------------------------------------------------------------------------|
|  tcs = timer clock cycles: 1 tcs is 12 nsec                                 |
|-----------------------------------------------------------------------------|
| 1 - Measure time to switch from ISR back to interrupted thread              |
| switching time is 107 tcs = 1337 nsec                                       |
|-----------------------------------------------------------------------------|

...

PROJECT EXECUTION SUCCESSFUL
```

The above regular expression can result in test case names like:

```text
1_measure_time_to_switch_from_isr_back_to_interrupted_thread_switching_time_is
```

The raw data will be logged as:

```text
test_case_id: 1 - Measure time to switch from ISR back to interrupted thread              |
| switching time is
```

!!! warning
    Notice how the regular expression has not closed the match at the end of
    the "line" but has continued on to the first non-matching character. The
    test case name then concatenates all whitespace and invalid characters to a
    single underscore. LAVA uses pexpect to perform output parsing. pexpect
    docs explain how to find line ending strings:
    <https://pexpect.readthedocs.io/en/stable/overview.html#find-the-end-of-line-cr-lf-conventions>

```python
r'(?P<test_case_id>\d+ *- [^-]+) (?P<measurement>\d+) tcs = [0-9]+ nsec'
```

The test_case_id will be formed from the match of the expression `\d+ *- [^-]+`
followed by a single space - but **only** if the rest of the expression matches
as well.

The measurement will be taken from the match of the expression `\d+` preceded
by a single space and followed by the **exact** string `tcs = ` which itself
must be followed by a number of digits, then a single space and finally the
**exact** string `nsec` - but only if the rest of the expression also matches.

See also: [Regular Expression HOWTO for Python3][regex]

### fixupdict

(optional) Maps non-standard result strings in test output to LAVA's expected
values. It is a translation map for raw result values.

```yaml title="fixupdict example"
fixupdict:
  PASSED: pass
  FAILED: fail
  SKIPPED: skip
```

### expected

(optional) Provide an expected test case list. After the test suite `end`
matches, missing test cases are reported as fail. Extra test cases are logged
as warnings.

```yaml title="Expected test cases"
- test:
    monitors:
    - name: "mcuboot_suite"
      start: "Execute test suites for the MCUBOOT area"
      end: "End of MCUBOOT test suites"
      pattern: "TEST: (?P<test_case_id>.+?) - (?P<result>(PASSED|FAILED|SKIPPED))"
      fixupdict:
         'PASSED': pass
         'FAILED': fail
         'SKIPPED': skip
      expected:
      - "tfm_mcuboot_integration_test_0001"
```

!!!note "Always reported"
    Expected test cases provided for the monitors are always reported, even if
    the tests are not executed due to earlier job errors.

### monitors

Multiple monitors can be defined for a single boot. LAVA processes each monitor
sequentially — waiting for the first monitor's `start` pattern, parsing until
its `end`, then moving to the next monitor.

```yaml title="Monitors for TF-M test suite"
- test:
    monitors:
    - name: "secure_regression_suite"
      start: "Execute test suites for the Secure area"
      end: "End of Secure test suites"
      pattern: "'(?P<test_case_id>TFM_S_[A-Z]+_TEST_[0-9]+)'.*?(?P<result>PASSED|FAILED|SKIPPED|Assertion failed)"
      fixupdict:
         'PASSED': pass
         'FAILED': fail
         'SKIPPED': skip
    - name: "non_secure_regression_suite"
      start: "Execute test suites for the Non-secure area"
      end: "End of Non-secure test suites"
      pattern: "TEST: (?P<test_case_id>.+?) - (?P<result>(PASSED|FAILED|SKIPPED))"
      fixupdict:
         'PASSED': pass
         'FAILED': fail
         'SKIPPED': skip

```

## Interactive

An interactive test action allows to interact with a non-POSIX shell or just
arbitrary interactive application. For instance, the shell of u-boot bootloader.

```yaml title="U-boot interactive tests"
actions:
- boot:
    method: bootloader
    bootloader: u-boot
    commands: []
    prompts:
    - "U-Boot>"

- test:
    interactive:
    - name: network
      prompts:
      - "U-Boot>"
      - "/ # "
      echo: discard
      script:
      - name: dhcp
        command: dhcp
        successes:
        - message: "DHCP client bound to address"
        failures:
        - message: "TIMEOUT"
          exception: InfrastructureError
          error: "dhcp failed"
      - name: setenv
        command: "setenv serverip {SERVER_IP}"
```

The workflow of the interactive test action is:

1. Send the `command` to the DUT, unless empty.
2. If `echo: discard` is specified, discard next output line (assumed to be an
   echo of the command).
3. Wait for a match from the `prompts`, `successes` or `failures`.
4. If a `name` is defined, log the result for this command (as soon as a prompt
   or a message is matched).
5. If a `successes` or `failures` was matched, wait for the `prompts` before
   proceeding.

!!! note
    The interactive test action expects the prompt to be already matched
    before it starts. If this is not the case, then you will to wait the prompt
    by adding an empty `command` directive as described below. Note that empty
    `command:` is different from empty string `command: ""`. In the latter
    case, a newline will be sent to device.

```yaml title="Wait for prompt first" hl_lines="9-10"
- test:
    interactive:
    - name: network
      prompts:
      - "U-Boot>"
      - "/ # "
      echo: discard
      script:
      - name: 'match-prompt'
        command:
      - name: setenv
        command: "setenv serverip {SERVER_IP}"
```

### name

A unique test suite name across all interactive test actions in the same
namespace.

### prompts

The list of possible prompts for the interactive session. In many cases, there
is just one prompt, but if shell has different prompts for different states, it
can be accommodated. Prompts can also include regular expressions, as any other
match strings.

### echo

If set to `discard`, after each sent `command` of a `script`, discard the next
output line (assumed to be an echo of the command). This option should be set
when interacting with shell (like u-boot shell) that will echo the command, to
avoid false positive matches. Note that this options applies to every `command`
in the script. If you need different value of this option for different
commands, you would need to group them in different `script`s.

### script

A list of commands to send and what kind of output to expect.

#### name

If present, log the result (pass/fail) of this command under the given name as
a test case). If not present, and the command fails, the entire test will
fail with `TestError`.

#### command

The command (string) to send to device, followed by newline. The command can use
variables that will be substituted with live data, like `{SERVER_IP}`. If
command value is empty (`command:` in YAML), nothing is sent, but output
matching (prompts/successes/failures) will be performed as usual.

#### successes

A list of dictionaries with a single `message` key. The message should be a list
of string or regex to match. It uses substring matching, so `message: 4` matches
"14", "41", etc.

#### failures

A list of dictionaries with:

* message (`str`): the string or regex to match (substring matching).
* exception (`str`, optional): if the message indicates a fatal problem,
  an exception can be raised. The exception can be one of `InfrastructureError`,
  `JobError`, or `TestError`.  If omitted, the failure is recorded as a failed
  test case without stopping the job.
* error (`str`, optional): custom exception message for the job log.

If `successes` is defined, but LAVA matches one of the prompts instead, an
error will be recorded (following the logic that the lack of expected success
output is an error). This means that in many cases you don't need to specify
`failures` - any output but the successes will be recorded as an error.

However, if `successes` is not defined, then matching a prompt will generate a
passing result. This is useful for interactive commands which don't generate
any output on success; of course, in this case you would need to specify
`failures` to catch them.

### expected

(optional) A list of expected test cases. After the script or the job
completes, missing test cases are reported as fail while extra test cases are
logged as warnings.

```yaml title="Expected test cases" hl_lines="9-11"
- test:
    interactive:
    - name: network
      prompts:
      - "U-Boot>"
      script:
      - name: setenv-serverip
        command: "setenv serverip {SERVER_IP}"
      expected:
      - setenv-serverip
```

!!!note "Always reported"
    The expected test cases are always reported, even if the tests are not
    executed due to earlier job errors.

## Services

The feature is disabled by default. It must be explicitly enabled in the device
dictionary by lab admin or device owner. And the worker that the device attached
to should have access to the Docker images needed by the services.

!!! danger
    Enabling the feature allows the users of the device to run any Docker
    containers with any permissions on the LAVA worker. Access to the device
    should be strictly restricted to trusted users using LAVA user groups.

```jinja2 title="Enable test services"
{% set allow_test_services = true %}
```

The services are defined in a `test` action using the `services` key.

```yaml title="Custom test services"
- test:
    services:
    - name: srv1
      from: git
      repository: https://example.com/org/srv1.git
      path: docker-compose.yml
    - name: srv2
      from: url
      repository: https://example.com/srv2.tar.gz
      path: docker-compose.yaml
      service: srv-name
      compression: gz
```

### name

Unique test service name.

### from

The type of the repository. Supported: `git` or `url`.

#### git

See [git](#git)

#### url

See [url](#url)

### repository

A publicly readable repository location.

### path

Path to the Docker Compose file within the repository.

### service

A specific service to start. If not set, all services in the compose file are
started.

### Lifecycle

Services started remain active until the end of the job. You can use command
`stop_test_services` to stop services earlier.

```yaml title="Stop test services"
- command:
    name: stop_test_services
```

--8<-- "refs.txt"
