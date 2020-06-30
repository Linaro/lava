Description
###########

Summary
*******

``lava-worker`` runs the connection to the lava server to
manage LAVA test jobs running on the reserved device, sending log
messages back to the master. ``lava-worker`` runs as a daemon.

Usage
*****

lava-worker [-h] [--hostname HOSTNAME] [--debug] [--worker-dir WORKER_DIR]
            --url URL --token TOKEN [--log-file LOG_FILE]
            [--level {DEBUG,ERROR,INFO,WARN}]

Options
*******

Options can be passed by editing /etc/default/lava-worker or
/etc/lava-dispatcher/lava-worker.

optional arguments:
  -h, --help            show this help message and exit
  --hostname HOSTNAME   Name of the worker
  --debug               Debug lava-run

storage:
  --worker-dir WORKER_DIR
                        Path to data storage

network:
  --url URL             Base URL of the server
  --token TOKEN         Worker token

logging:
  --log-file LOG_FILE   Log file for the worker logs
  --level {DEBUG,ERROR,INFO,WARN}, -l {DEBUG,ERROR,INFO,WARN}
                        Log level, default to INFO
