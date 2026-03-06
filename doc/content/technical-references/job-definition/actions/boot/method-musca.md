# Musca

The `musca` boot method is used to boot Musca devices deployed by the
[`musca`](../deploy/to-musca.md) deployment method.

```yaml
- deploy:
    to: musca
    images:
      test_binary:
        url: https://storage.lavacloud.io/health-checks/musca-b/tfm.hex

- boot:
    method: musca
```

Unlike the [`minimal`](./method-minimal.md) boot method, the board has to be
powered on before the serial will be available as the board is powered by the
USB that provides the serial connection also. Therefore, the board is powered on
then connection to the serial is made.

## prompts

Optional. If the test binary has output, `prompts` can be used to wait for a
specific string from the serial output before continuing.

```yaml
- boot:
    method: musca
    prompts: "string"
```

## monitors

No shell is expected, and no boot string is checked. All checking should be
done with [test monitors](../test.md#monitors).

## Job example

```yaml
job_name: musca-b-health-check
device_type: musca-b
priority: medium
visibility: public

timeouts:
  job:
    minutes: 20
  action:
    minutes: 10

actions:
    - deploy:
        to: musca
        images:
          test_binary:
            url: https://storage.lavacloud.io/health-checks/musca-b/tfm.hex

    - boot:
        method: musca

    - test:
        monitors:
        - name: "Secure_Test_Suites_Summary"
          start: "Non-Secure system"
          end: "starting\\.{3}"
          pattern: "Non-Secure system starting\\.{3}"
          fixupdict:
              '!': pass
              '': fail
```
