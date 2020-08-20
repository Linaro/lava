
Description
###########

Summary
*******

``lava-run`` runs a LAVA test job on the reserved device, as
scheduled by the ``lava-scheduler`` and publish the test result back to
the server. Jobs are scheduled by the server but can also be run by
calling ``lava-run`` directly.

You can see an up-to-date list of supported target devices by looking
at the device types on the relevant server.

Usage
*****

lava-run [-h] --job-id ID --output-dir DIR [--validate]
         [--url URL] [--token token]
         --device PATH [--dispatcher PATH] [--env-dut PATH]
         [--debug] definition

Options
*******

positional arguments:
  definition         job definition

optional arguments:
  -h, --help         show this help message and exit
  --job-id ID        Job identifier. This alters process name for easier debugging
  --output-dir DIR   Directory for temporary resources
  --validate         validate the job file, do not execute any steps. The description is saved into description.yaml
  --debug            Start remote pdb right before running the job, for debugging

logging:
  --url URL          URL of the server to send logs
  --token token      token for server authentication

configuration files:
  --device PATH      Device configuration
  --dispatcher PATH  Dispatcher configuration
  --env-dut PATH     DUT environment

Useful links
############

For more information on writing job definition and tests, look at:

https://validation.linaro.org/static/docs/v2/first-job.html

https://validation.linaro.org/static/docs/v2/contents.html#writing-tests-for-lava
