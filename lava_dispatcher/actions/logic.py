from lava_dispatcher.action import Action


class RepeatAction(Action):

    name = 'repeat'


class IfAction(Action):

    name = 'if'


class IncludeAction(Action):

    name = 'include'


class InParallelAction(Action):

    name = 'in_parallel'
