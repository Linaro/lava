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

--8<-- "refs.txt"
