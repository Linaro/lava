# Testing LAVA

## Code style

We use [black] to format the LAVA source code.

The GitLab CI will run black on every merge request.

You can run it locally:

```shell
apt-get install black
black lava/
```

## Unittests

We use [pytest] for the python test harness.

To run the full test suite:

```shell
python3 -m pytest -v tests/
```

You can execute every tests that are defined in a given file:

```shell
python3 -m pytest -v tests/lava_dispatcher/test_utils.py
```

You can also execute a specific test:
```shell
python3 -m pytest -v tests/lava_dispatcher/test_utils.py::test_simple_clone
```

## Static analysis

We use [pylint] and [bandit] for static analysis.

You can run them locally:

```shell
.gitlab-ci/analyze/pylint.sh
bandit -r .
```

## Job schema

If you change the device or job schemas, you will have to ensure that the device and job schemas are valid.

This is checked by:

```shell
```

--8<-- "refs.txt"
