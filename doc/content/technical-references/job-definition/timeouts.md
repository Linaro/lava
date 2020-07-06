# Timeouts

## Timeout syntax

A timeout is a dictionary with unit and value:

```yaml
timeout:
  <unit>: <value>
```

Valid units are `seconds`, `minutes`, `hours` and `days` while the value should be an integer.

## Job timeout

The entire job will have an overall timeout. The job will fail if this timeout
is exceeded, whether or not any other timeout is longer.

```yaml
timeouts:
  job:
    minutes: 15
```

## Action timeout

Each action of a job will have a timeout. The action will not run longer than the defined timeout.

To define the timeout, you should add a `timeout` dictionary to the action definition:

```yaml
actions:
- deploy:
    timeout:
      minutes: 5
    [...]
```

!!! warning "action timeout"
    No action timeout can be larger than the job timeout.
    If the action timeout is larger than the job timeout, LAVA will set the
    action timeout to the job timeout and warn during validation.


### Default timeout

You can define the default duration of every action:

```yaml
timeouts:
  action:
    seconds: 60
```

You can also define individual action timeout in the root timeout dictionary:

```yaml
timeouts:
  actions:
    extract-nfsrootfs:
      seconds: 60
```

## Connection timeout

When an action interact with the DUT, this action will use the
`connection_timeout`. Each interaction with the DUT should take less than the
`connection_timeout` duration.

You can define the default duration of every connection timeout:

```yaml
timeouts:
  connection:
    seconds: 60
```

You can also define individual connection timeout in the root timeout dictionary:

```yaml
timeouts:
  connections:
    lava-test-shell:
      seconds: 60
```


## Skipping timeout

!!! warning "TODO"
