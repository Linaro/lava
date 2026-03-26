# Job results

A test result in a LAVA job is called a test case that include a result. Each
test case can optionally include a measurement and a units string. Test cases
are aggregated into a test suite. Multiple test suites can be generated for each
test job.

## Test suite

The name of a test suite is defined in the test job definition. LAVA creates
one test suite for each [test](./job-definition/actions/test.md) definition,
using its `name` field. For the
[`definitions`](./job-definition/actions/test.md#definitions) action, LAVA
prepends a zero-based sequence number to the `name` to ensure test suite is
unique within the job.

Every test job also generates a reserved `lava` test suite that contains results
produced by the job actions.

## Test set

Test Set is optional and allows test writers to subdivide individual results
within a single Lava test definition using an arbitrary label. This is useful
when the same test is run multiple times with different parameters.

See [lava-test-set](../user/basic-tutorials/test-definition.md#lava-test-set) for
recording a test set.

## Test case

Each test case has a `name` and a `result`. Optionally it can have a
`measurement` and `units`.

See [lava-test-case](../user/basic-tutorials/test-definition.md#lava-test-case)
for recording a test result.

!!! note
    - Whitespace is not allowed in test case name.
    - Supported result types are: `pass`, `fail`, `skip` or `unknown`.

## Retrieving results

### API

See `/api/v0.2/jobs/` for the endpoints that can be used to retrieve LAVA job
results through the REST API.

### URL

LAVA job results also can be retrieved via the following simple URLs:

| URL | Description |
| --- | ----------- |
| `/results/<job_id>/csv` | All job results as CSV |
| `/results/<job_id>/yaml` | All job results as YAML |
| `/results/<job_id>/yaml_summary` | All test suite names as YAML |
| `/results/<job_id>/<suite_name>/csv` | Results for a specific test suite as CSV |
| `/results/<job_id>/<suite_name>/yaml` | Results for a specific test suite as YAML |
| `/results/testcase/<testcase_id>/yaml` | Result for a specific test case as YAML |
