# fvp

The `fvp` boot method allows you to run Fixed Virtual Platforms.

```yaml
- boot:
    method: fvp
    docker:
      name: "fvp_foundation:11.8"
      local: true
    image: /path/to/FVP_Binary
    ubl_license: "/root/ubl.lic"
    arguments:
      - "-C board.virtioblockdevice.image_path={DISK}"
    version_string: Fast Models [^\n]+
    console_string: 'terminal_0: Listening for serial connection on port (?P<PORT>\d+)'
    feedbacks:
    - '(?P<NAME>terminal_1): Listening for serial connection on port (?P<PORT>\d+)'
    - '(?P<NAME>terminal_2): Listening for serial connection on port (?P<PORT>\d+)'
    - '(?P<NAME>terminal_3): Listening for serial connection on port (?P<PORT>\d+)'
```

This boot method will launch the FVP binary
(already present in the docker image) specified with the `image` key with the
`arguments` as parameters.

!!! note
    The docker image must have the fastmodel in it and must have the required
    tools, such as `telnet`.

## ubl_license

(optional) Specifies a Universal Base License (UBL) for FVP models. The value
can be either:

- A file path to a license file
- A license activation code matches the pattern `XXXXX-XXXXX-XXXXX-XXXXX-XXXXX`

!!! note
    Using a license file is recommended so you don't hit the activation limit
    set on the license server by running many jobs in parallel that try to
    connect to the server for activation.

## arguments

A list of arguments passed to the FVP binary.

You can use `{IMAGE_NAME}` which will be replaced with the path to the image
with the same key under `images` in the previous `fvp` deploy stage.
`{ARTIFACT_DIR}` can also be used for the directory where all images are
deployed.

!!! note
    Previous to running an `fvp` boot, you should run an `fvp` deploy.

## version_string

A regular expression pattern defaults to `Fast Models[^\n]+` for matching the
FVP version output. The version output is saved as extra information of test
result `lava/fvp-version`.

## console_string

A required regular expression pattern that matches console output from the FVP
model. This pattern must contain a named group `(?P<PORT>\d+)` to extract the
serial port number that the FVP terminal is listening on. LAVA uses this port
number to establish a connection to the FVP console.

## feedbacks

Sometimes models offer more than one console that produces useful output. LAVA
can only write to one console at a time. Reading can be done from multiple
consoles. In some cases it's essential to read from all consoles to prevent
model from hanging. This happens when internal model buffer is not able to
accept more output because previously generated output is not consumed. FVP
boot method allows to define additional regexes to match more than one console.
This is done with the `feedbacks` keyword.

Feedbacks will be read twice during boot process (before matching login prompt)
and periodically during test-shell.

## erpc_app

You can provide `erpc_app: image_key` field to run a eRPC app. Both the server
and test apps must be deployed in advance. The `image_key` should be the name
of the test app. eRPC-related parameters for communication between the apps
should be configured at build time. Using a separate UART device is recommended
to avoid collision with other data being sent on UART. A `monitors` test action
can be defined right after the boot action to enable log parsing and wait for
run completion.

Example definition:

```yaml
actions:
- deploy:
    timeout:
      minutes: 5
    to: fvp
    images:
      APP:
        url: https://example.com/bl2.axf
      SERVER_APP:
        url: https://example.com/tfm_s_ns_signed.bin
      TEST_APP:
        url: https://example.com/erpc_main

- boot:
    timeout:
      minutes: 5
    method: fvp
    docker:
      name: localhost/fvp-std-lib:erpc
      local: true
    version_string: "Fast Models [^\\n]+"
    image: "/opt/model/FVP_ARM_Std_Library/FVP_MPS2/FVP_MPS2_AEMv8M"
    ubl_license: "/root/swskt-linaro-root-20241031-365d.lic"
    arguments:
    - "--parameter fvp_mps2.platform_type=2"
    - "--parameter cpu0.baseline=0"
    - "--parameter cpu0.INITVTOR_S=0x10000000"
    - "--parameter cpu0.semihosting-enable=0"
    - "--parameter fvp_mps2.DISABLE_GATING=0"
    - "--parameter fvp_mps2.telnetterminal0.start_telnet=1"
    - "--parameter fvp_mps2.telnetterminal1.start_telnet=0"
    - "--parameter fvp_mps2.telnetterminal2.start_telnet=0"
    - "--parameter fvp_mps2.telnetterminal0.quiet=0"
    - "--parameter fvp_mps2.telnetterminal1.quiet=1"
    - "--parameter fvp_mps2.telnetterminal2.quiet=1"
    - "--parameter fvp_mps2.telnetterminal0.start_port=5000"
    - "--parameter fvp_mps2.telnetterminal1.start_port=5001"
    - "--parameter fvp_mps2.telnetterminal1.mode=raw"
    - "--parameter fvp_mps2.UART1.unbuffered_output=1"
    - "--application cpu0={APP}"
    - "--data cpu0={SERVER_APP}@0x10080000"
    - "-M 1"
    console_string: 'telnetterminal0: Listening for serial connection on port (?P<PORT>\d+)'
    use_telnet: true
    prompts:
    - "Non-Secure system starting..."
    erpc_app: "TEST_APP"
```

## commands

(optional) A list of shell commands to execute in the FVP Docker container after
the FVP model has started. These commands are joined with `&&` and executed
sequentially using `docker exec --tty fvp_container sh -c 'joined_commands'`.

Example definition:

```yaml
- boot:
    method: fvp
    docker:
      name: fvp_rd_v3_r1:xvfb
      local: true
    image: /opt/model/FVP_RD_V3_R1/models/Linux64_GCC-9.3/FVP_RD_V3_R1
    version_string: Fast Models [^\n]+
    timeout:
      minutes: 15
    console_string: 'terminal0: Listening for serial connection on port (?P<PORT>\d+)'
    arguments:
    - -C socket0.css0.sysctrl.rse.rom.raw_image='{ROM}'
    - -C socket0.css1.sysctrl.rse.rom.raw_image='{ROM}'
    - -C socket0.css0.sysctrl.rse.intchecker.ICBC_RESET_VALUE=0x0000011B
    - -C socket0.css1.sysctrl.rse.intchecker.ICBC_RESET_VALUE=0x0000011B
    - -C socket0.board0.rse2rse_mhu0.NUM_CH=16
    - -C socket0.board1.rse2rse_mhu0.NUM_CH=16
    - -C socket0.css0.sysctrl.rse.DISABLE_GATING=true
    - -C socket0.css1.sysctrl.rse.DISABLE_GATING=true
    - -C socket0.css0.sysctrl.rse_uart.out_file=rse_uart_css0.log
    - -C socket0.css0.sysctrl.rse_uart.unbuffered_output=1
    - -C socket0.css0.sysctrl.rse_uart.uart_enable=true
    - -C socket0.css1.sysctrl.rse_uart.out_file=rse_uart_css1.log
    - -C socket0.css1.sysctrl.rse_uart.unbuffered_output=1
    - -C socket0.css1.sysctrl.rse_uart.uart_enable=true
    - -C socket0.css0.sysctrl.otpw.GP_AON_0_INIT_VAL=0x80000000
    - -C socket0.css1.sysctrl.otpw.GP_AON_0_INIT_VAL=0x80000000
    - --data socket0.css0.sysctrl.rse.cpu='{TESTS}'@0x31000400
    - -IRp
    commands:
    - export PYTHONPATH=$PYTHONPATH:/opt/model/FVP_RD_V3_R1/Iris/Python/
    - python3 <path>/test_dcsu.py --backend iris --iris_dcsu_component_string socket0.css0.sysctrl.dcsu
```

A `monitors` test action can be defined after the boot action to enable
log parsing and wait for the commands to finish.

```yaml
- test:
    timeout:
      minutes: 5
    monitors:
    - name: "rse_bl1_tests"
      start: "INFO:DCSU:Using iris backend"
      end: "TEST: Send completion PASSED"
      pattern: 'TEST: (?P<test_case_id>.+?) (?P<result>PASSED|FAILED|SKIPPED)'
      fixupdict:
         PASSED: pass
         FAILED: fail
         SKIPPED: skip
```
