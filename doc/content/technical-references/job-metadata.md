# Job metadata

The [`metadata`](./job-definition/job.md#metadata) dictionary of a job
definition is stored with the test job. It is meant for the information that
identifies what a job was testing, for example a build id, a git branch or a
toolchain version:

```yaml
metadata:
  build_id: 1234
  branch: release/1.0
  build-url: https://ci.example.com/builds/42
```

Metadata is read when the job is submitted and is never updated afterwards.
Multinode jobs copy the metadata into every sub job.

## Value types

Scalar values are stored as strings, so a filter does not have to know which
type YAML gave them: `build_id: 1234` and `build_id: "1234"` are both matched
by `?metadata__build_id=1234`. Booleans are stored as `true` and `false`.
Dictionaries and lists are kept as they are.

## Retrieving metadata

The metadata of a job is part of the job object in the REST API and is also
available on its own:

```shell
curl https://validation.linaro.org/api/v0.2/jobs/1234/metadata/
```

The results page of a job has a **Job metadata** button that downloads the same
data as YAML.

## Filtering jobs by metadata

Any metadata key can be used as a `metadata__<key>` filter on the jobs
endpoint:

```shell
curl "https://validation.linaro.org/api/v0.2/jobs/?metadata__build_id=1234"
```

Nested dictionaries are reached by adding the keys in order, so
`metadata__build__id=1234` matches:

```yaml
metadata:
  build:
    id: 1234
```

The key can be followed by a lookup. Without one, `exact` is used:

| Lookup        | Description                                     |
| ------------- | ----------------------------------------------- |
| `exact`       | Exact match, the default                        |
| `iexact`      | Exact match, ignoring case                      |
| `icontains`   | Contains the value, ignoring case               |
| `startswith`  | Starts with the value                           |
| `istartswith` | Starts with the value, ignoring case            |
| `endswith`    | Ends with the value                             |
| `iendswith`   | Ends with the value, ignoring case              |
| `in`          | Matches one of the values, separated by commas  |
| `isnull`      | The key is (not) set                            |
| `regex`       | Matches the regular expression                  |
| `iregex`      | Matches the regular expression, ignoring case   |

```shell
curl "https://validation.linaro.org/api/v0.2/jobs/?metadata__branch__startswith=release/"
curl "https://validation.linaro.org/api/v0.2/jobs/?metadata__build_id__in=1234,5678"
```

Several metadata parameters can be combined with any other job filter. Only the
jobs matching all of them are returned:

```shell
curl "https://validation.linaro.org/api/v0.2/jobs/?metadata__branch=main&metadata__build_id=1234&health=Complete"
```

These lookups work on the metadata dictionary as a whole:

| Filter                    | Description                                    |
| ------------------------- | ---------------------------------------------- |
| `metadata__has_key`       | Has this key                                   |
| `metadata__has_keys`      | Has all of these keys, separated by commas     |
| `metadata__has_any_keys`  | Has any of these keys, separated by commas     |
| `metadata__contains`      | Metadata contains this JSON object             |

```shell
curl "https://validation.linaro.org/api/v0.2/jobs/?metadata__has_key=build_id"
curl -G https://validation.linaro.org/api/v0.2/jobs/ \
     --data-urlencode 'metadata__contains={"branch": "main", "build_id": "1234"}'
```

!!! note "Performance"
    On PostgreSQL, exact matches and the dictionary lookups use the index on
    the metadata column. The other lookups cannot, so they are much slower on
    instances with a large number of test jobs. Combine them with an exact
    match or with any other job filter whenever possible.

!!! warning "Jobs submitted before the upgrade"
    Metadata is stored at submission time. Jobs submitted before the instance
    was upgraded to the LAVA version that introduced this feature have no
    metadata until the administrator runs
    [`lava-server manage jobs backfill-metadata`](../admin/advanced-tutorials/backfill-job-metadata.md).
