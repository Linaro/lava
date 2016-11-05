.. _dispatcher_actions:

Dispatcher Action Reference
###########################

Job submissions for the pipeline dispatcher use YAML and test writers can
create a pipeline of actions based on three basic types. Parameters in the YAML
and in the device configuration are used to select the relevant Strategy for
the job and this determines which actions are added to the pipeline.

In addition, the job has some general parameters, including a job name
and :ref:`dispatcher_timeouts`.

Deploy Actions
**************

.. toctree::
   :maxdepth: 6

   actions-deploy.rst

Boot Actions
************

.. toctree::
   :maxdepth: 6

   actions-boot.rst

Test Actions
************

.. toctree::
   :maxdepth: 6

   actions-test.rst

Other test job elements
***********************

.. toctree::
   :maxdepth: 6

   actions-repeats.rst
   actions-protocols.rst
   actions-timeout.rst
   user-notifications.rst

.. FIXME need to add notifications and metadata

Further Examples
****************

The number and range of test jobs is constantly increasing. The LAVA software
team develop functional tests in a dedicated git repository:
https://git.linaro.org/lava-team/refactoring.git Tests can then migrate into
standard tests and examples in the documentation. Even so, not all dispatcher
actions have a matching example.

.. seealso:: :ref:`using_gold_standard_files`
