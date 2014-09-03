from lava_dispatcher.pipeline.action import Action


class DeployAction(Action):
    """
    Base class for all actions which deploy files
    to media on a device under test.
    The subclass selected to do the work will be the
    subclass returning True in the accepts(device, image)
    function.
    Each new subclass needs a unit test to ensure it is
    reliably selected for the correct deployment and not
    selected for an invalid deployment or a deployment
    accepted by a different subclass.
    """

    name = 'deploy'
