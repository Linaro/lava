
Description
###########

Summary
*******

``lava-dispatch`` runs a LAVA test job on the reserved device, as
scheduled by the ``lava-server`` and publish the test result back to
the server. Jobs are scheduled by the server but can also be run by
calling ``lava-dispatch`` directly.

You can see an up-to-date list of supported target devices by looking
at the device types on the relevant server.

Usage
*****

lava dispatch [-h] [--config-dir CONFIG_DIR] [--oob-fd OOB_FD]
[--output-dir OUTPUT_DIR] [--validate] [--job-id JOB_ID]
[--target TARGET]
JOB

Options
*******

positional arguments:
  JOB                   Test scenario JSON file

optional arguments:
  -h, --help            show this help message and exit
  --config-dir CONFIG_DIR
                        Configuration directory override
  --oob-fd OOB_FD       Used internally by LAVA scheduler.
  --output-dir OUTPUT_DIR
                        Directory to put structured output in.
  --validate            Just validate the job file, do not execute any steps.
  --job-id JOB_ID       Set the scheduler job identifier. This alters process
                        name for easier debugging
  --target TARGET       Run the job on a specific target device

LAVA test definitions
#####################

A LAVA Test Definition comprises of two parts:

* the data to setup the test, expressed as a JSON file.
* the instructions to run inside the test, expressed as a YAML file.

This allows the same tests to be easily migrated to a range of different
devices, environments and purposes by using the same YAML files in
multiple JSON files. It also allows tests to be built from a range of
components by aggregating YAML files inside a single JSON file.

Contents of the JSON file
#########################

The JSON file is submitted to the LAVA server and contains:

* Demarcation as a health check or a user test.
* The default timeout of each action within the test.
* The logging level for the test, DEBUG or INFO.
* The name of the test, shown in the list of jobs.
* The location of all support files.
* All parameters necessary to use the support files.
* The declaration of which device(s) to use for the test.
* The location to which the results should be uploaded.
* The JSON determines how the test is deployed onto the device and
  where to find the tests to be run.

Basic JSON file
###############

Your first LAVA test should use the ``DEBUG`` logging level so that it
is easier to see what is happening.

A suitable ``timeout`` for your first tests is 900 seconds.

Make the ``job_name`` descriptive and explanatory, you will want to be
able to tell which job is which when reviewing the results.

Make sure the ``device_type`` matches exactly with one of the suitable
device types listed on the server to which you want to submit this job.

Change the stream to one to which you are allowed to upload results, on
your chosen server.

::

 {
   "health_check": false,
   "logging_level": "DEBUG",
   "timeout": 900,
   "job_name": "kvm-basic-test",
   "device_type": "kvm",
   "actions": [
       {
           "command": "deploy_linaro_image",
           "parameters": {
               "image": "http://images.validation.linaro.org/kvm-debian-wheezy.img.gz"
           }
       },
       {
           "command": "lava_test_shell",
           "parameters": {
               "testdef_repos": [
                   {
                       "git-repo": "git://git.linaro.org/qa/test-definitions.git",
                       "testdef": "ubuntu/smoke-tests-basic.yaml"
                   }
               ],
               "timeout": 900
           }
       },
       {
           "command": "submit_results_on_host",
           "parameters": {
               "stream": "/anonymous/example/",
               "server": "http://localhost/RPC2/"
           }
       }
   ]
 }

Note
####

Always check your JSON syntax. A useful site for this is http://jsonlint.com.

Useful links
############

http://validation.linaro.org/static/docs/writing-tests.html

http://validation.linaro.org/

http://validation.linaro.org/static/docs/overview.html

http://www.linaro.org/engineering/validation
