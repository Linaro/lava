.. _command_action:

Command Action Reference
########################

The ``command`` action is used to execute a pre-defined command on the
dispatcher itself.
A typical use case would be to set the bootmode for a board by controlling a
relay.

In order to use the action, the action block should only define the name of the
command to execute.

Command is the top level action.

.. code-block:: yaml

  - command:
      name: set_boot_to_nand


Admin Setup
***********

In order to use a command action, admins should add the command name to the **device dictionary**.

.. code-block:: jinja

  {% set user_commands = {'set_boot_to_qspi': {'do': 'webrelay --host 192.168.0.15 --port 1234 --relay 1 on',
                                               'undo': 'webrelay --host 192.168.0.15 --port 1234 --relay 1 off'},
                          'set_boot_to_nand': {'do': 'webrelay --host 192.168.0.15 --port 1234 --relay 1 off',
                                               'undo': 'webrelay --host 192.168.0.15 --port 1234 --relay 1 off'}} %}

**user_commands** is a dictionary of commands where the key will be used in the job definition.

if the command should be undone when the job finishes, admins should add a **undo** command.
