from lava_dispatcher.pipeline import *
import logging


#logging.root.setLevel('DEBUG')

device = Device('arndale01')

image = None  # TODO

pipe = Pipeline()
pipe.add_action(ConnectToSerial())
#pipe.add_action(ConnectViaSSH())
pipe.add_action(ExpectShellSession())
pipe.add_action(RunShellCommand())

job = Job(device, image, pipe)

job.run()
