# Adding new Actions

The expectation is that new tasks for the LAVA dispatcher will be created
by adding more specialist Actions and organizing the existing Action
classes into a new pipeline for the new task.

## Two-step process

Adding new behavior is a two-step process:

1. **Always** add a new Action, usually with an internal pipeline, to
   implement the new behavior.
2. Add a new Strategy class which creates a suitable pipeline to use
   that Action.

A test Job will consist of multiple strategies, one for each of the
listed *actions* in the YAML file. Typically, this may include a
Deployment strategy, a Boot strategy and a Test strategy. Jobs can have
multiple deployment, boot, or test actions.

## Guidelines for adding new actions

1. A Strategy class is simply a way to `select()` which top level Action
   class is instantiated.

2. Ensure that the `accepts()` routine can uniquely identify this strategy
   without interfering with other strategies.

3. A top level Action class creates an internal pipeline in `populate()`.
   Actions are added to the internal pipeline to do the rest of the work.

4. A top level Action will generally have a basic `run()` function which
   calls `run_actions()` on the internal pipeline.

5. Respect the existing classes — reuse wherever possible and keep all
   classes as pure as possible. There should be one class for each type
   of operation and no more.

6. Expose all configuration in the device or job definitions, not python.
   Extend the device or job schemas if new values are needed.

7. Take care with YAML structure. Always check your YAML changes in the
   [Online YAML Parser](http://yaml-online-parser.appspot.com/?yaml=&type=json).

8. Cherry-pick existing classes alongside new classes to create new
   pipelines and keep all Action classes to a single operation.

9. Code defensively:
    * Check that parameters exist in validation steps.
    * Call `super()` on the base class `validate()` in each `Action.validate()`.
    * Handle missing data in the dynamic context. Don’t assume namespace
      data from earlier actions is always present.
    * Use `cleanup()` and keep actions idempotent.

## Adding retry actions

For a `RetryAction` to validate, the `RetryAction` subclass must be a
wrapper class around a new pipeline to allow the `RetryAction.run()`
function to handle all the retry functionality in one place.

An Action which needs to support `failure_retry` or which wants to use
`RetryAction` support internally, needs a new class added which derives
from `RetryAction`, sets a useful name, summary and description and
defines a `populate()` function which creates the pipeline.

## Always add unit tests for new actions

Wherever a new class is added, that new class should be tested. Always
create a new file in the tests directory for new functionality.

All unit tests need to be in a file with the `test_` prefix and add a
new YAML file to the `sample_jobs` so that the strategies to select the
new code can be tested.

To run a single unit-test, for example `test_pipeline` in a class called
`TestFlasher` in a file called `test_flasher.py`, use:

```shell
pytest tests/lava_dispatcher/test_flasher.py::TestFlasher::test_pipeline
```

## Coding conventions

When adding or modifying `run`, `validate`, `populate` or `cleanup`
functions, always ensure that `super` is called appropriately:

```python
super().validate()
```

When adding or modifying `run` functions in subclasses of `Action`,
always ensure that each return point returns the `connection` object:

```python
connection = super().run(connection, max_end_time)
# Use the connection or initiate a new one.
return connection
```

When adding new classes, use hyphens (`-`) as separators in `self.name`,
not underscores (`_`). Action names need to all be lowercase:

```python
self.name = 'do-something-at-runtime'
```

Use namespaces for all dynamic data. Parameters of actions are
**immutable**. Use the namespace functions when an action needs to store
dynamic data:

```python
self.set_namespace_data(
    action="run-fvp",
    label="fvp",
    key="serial_port",
    value=serial_port,
)
```

The data can be retrieved in the following actions in the pipeline:

```python
serial_port = self.get_namespace_data(
            action="run-fvp", label="fvp", key="serial_port"
        )
```
