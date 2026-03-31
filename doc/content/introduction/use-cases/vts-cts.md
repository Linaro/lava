# VTS / CTS

The Android [Vendor Test Suite (VTS)](https://source.android.com/docs/core/tests/vts)
and
[Compatibility Test Suite (CTS)](https://source.android.com/docs/compatibility/cts)
are test frameworks used to validate Android device implementations.

LAVA provides sophisticated methods for deploying and booting Android images, as
well as for executing VTS/CTS test suites.

```yaml
device_type: dragonboard-845c
job_name: android-mainline-cts-test

timeouts:
  job:
    minutes: 600
  connection:
    minutes: 2
  actions:
    finalize:
      seconds: 60

priority: 50
visibility: public

context:
  test_character_delay: 10

secrets:
  SQUAD_ARCHIVE_SUBMIT_TOKEN: SQUAD_ARCHIVE_SUBMIT_TOKEN

actions:
- deploy:
    to: fastboot
    docker:
      image: linaro/lava-android-test:focal-2024.02.20-01
      local: true
    images:
      partition:0:
        url: https://example.com/gpt_both0.bin
      boot:
        url: https://example.com/boot.img
      super:
        url: https://example.com/super.img
      vendor_boot:
        url: https://example.com/vendor_boot.img
      userdata:
        url: https://example.com/userdata.img
    timeout:
      minutes: 20

- test:
    docker:
      image: linaro/lava-android-test:focal-2024.02.20-01
      local: true
    definitions:
    - from: inline
      path: format-metatdata.yaml
      name: format-metatdata
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: format-metatdata
          description: format-metatdata
        run:
          steps:
          - lava-test-case "format-metadata" --shell fastboot format:ext4 metadata
    timeout:
      minutes: 5

- test:
    docker:
      image: linaro/lava-android-test:focal-2024.02.20-01
      local: true
    definitions:
    - from: inline
      path: select-display-panel.yaml
      name: select-display-panel
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: select-display-panel
          description: select-display-panel
        run:
          steps:
          - lava-test-case "select-display-panel-1" --shell fastboot oem select-display-panel
            hdmi
          - lava-test-case "reboot-bootloader-1" --shell fastboot reboot bootloader
          - lava-test-case "select-display-panel-2" --shell fastboot oem select-display-panel
            hdmi
          - lava-test-case "reboot-bootloader-2" --shell fastboot reboot bootloader
          - lava-test-case "select-display-panel-3" --shell fastboot oem select-display-panel
            hdmi
          - lava-test-case "reboot" --shell fastboot reboot
    timeout:
      minutes: 5

- boot:
    method: fastboot
    docker:
      image: linaro/lava-android-test:focal-2024.02.20-01
      local: true
    prompts:
    - console:/
    - root@(.*):[/~]#
    timeout:
      minutes: 15

- test:
    timeout:
      minutes: 10
    interactive:
    - name: sleep-before-adb-available
      prompts:
      - console:/
      - root@(.*):[/~]#
      script:
      - command: echo ===========================
      - command: i=0 && while ! getprop sys.boot_completed|grep 1 && [ $i -le 30 ];
          do let i=i+1; echo sleep $i*10s for sys.boot_completed; sleep 10; done;
          echo "for prompt";
      - command: if ! getprop sys.boot_completed|grep 1 ; then logcat -d; echo "Failed
          to boot successfully"; exit 1; fi
      - command: echo ===========================
      - command: i=0 && while ! getprop init.svc.adbd|grep running && [ $i -le 15
          ]; do let i=i+1; echo sleep $i*10s for init.svc.adbd; sleep 10; done; echo
          "for prompt";
      - command: if ! getprop init.svc.adbd|grep running; then logcat -d; echo "Failed
          to have adbd running"; exit 1; fi
      - command: echo ===========================
      - command: getprop | grep adb
      - command: echo ===========================

- test:
    docker:
      image: linaro/lava-android-test:focal-2024.02.20-01
      local: true
    definitions:
    - from: inline
      path: android-boot.yaml
      name: android-boot
      repository:
        metadata:
          format: Lava-Test Test Definition 1.0
          name: android-boot
          description: android-boot
        run:
          steps:
          - lava-test-case "android-boot-wait-for-device" --shell adb wait-for-device
          - lava-test-case "android-boot-boot-completed" --shell "while ! adb shell
            getprop sys.boot_completed|grep 1; do sleep 2; done"
          - lava-test-case "android-boot-set-power-stayon" --shell adb shell su 0
            svc power stayon true
          - lava-test-case "android-boot-screencap" --shell adb shell screencap -p
            /data/local/tmp/screencap.png
          - lava-test-case "android-boot-fstab" --shell adb shell "su 0 cat /vendor/etc/fstab.*"
          - lava-test-case "android-boot-kernel-version" --shell adb shell su 0 cat
            /proc/version
          - lava-test-case "android-boot-kernel-cmdline" --shell adb shell su 0 cat
            /proc/cmdline
    timeout:
      minutes: 10

- test:
    docker:
      image: linaro/lava-android-test:focal-2024.02.20-01
      local: true
    definitions:
    - repository: https://github.com/Linaro/test-definitions.git
      from: git
      path: automated/android/noninteractive-tradefed/tradefed.yaml
      params:
        TEST_PARAMS: cts --include-filter CtsAslrMallocTestCases --include-filter
          CtsBionicTestCases --include-filter CtsBluetoothTestCases --include-filter
          CtsCameraTestCases --include-filter CtsDisplayTestCases --include-filter
          CtsDramTestCases --include-filter CtsDrmTestCases --include-filter CtsGraphicsTestCases
          --include-filter CtsHardwareTestCases --include-filter CtsJankDeviceTestCases
          --include-filter CtsJniTestCases --include-filter CtsLibcoreLegacy22TestCases
          --include-filter CtsLibcoreTestCases --include-filter CtsMonkeyTestCases
          --include-filter CtsOsTestCases --include-filter CtsSystemUiTestCases --include-filter
          CtsSystemUiRenderingTestCases --include-filter CtsUsbTests --exclude-filter
          "CtsOsTestCases android.os.cts.BuildVersionTest#testBuildFingerprint" --exclude-filter
          "CtsOsTestCases android.os.cts.SecurityFeaturesTest#testPrctlDumpable" --disable-reboot
        TEST_URL: https://example.com/android-cts.zip
        TEST_PATH: android-cts
        RESULTS_FORMAT: aggregated
        ANDROID_VERSION: aosp-main
        SQUAD_UPLOAD_URL: https://qa-reports.linaro.org/api/submit/android-lkft/mainline-gki-16k-aosp-master-db845c/6.12.0-b405a1c95660/dragonboard-845c
        INTERNET_ACCESS: 'true'
      name: cts-lkft
    timeout:
      minutes: 480
```

See [tradefed test definition](https://github.com/Linaro/test-definitions/blob/master/automated/android/noninteractive-tradefed/tradefed.yaml)
for what each test parameter does.
