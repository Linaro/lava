# Test definitions

The [test definition](../../technical-references/test-definition.md) is a `yaml` file that describe the tests that you want LAVA
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

## Install
!!! tip "install"
    LAVA can also install some packages or sources before running the tests.
    See the [technical documentation](../../technical-references/test-definition.md)
    for more information.

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
