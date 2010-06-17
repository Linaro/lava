from .launch_control.sample import QualitativeSample

class Factory(object):
    """Helper class for making objects"""

    def make_qualitative_sample(self, test_result=None, **kwargs):
        if test_result is None:
            test_result = 'pass'
        return QualitativeSample(test_result, **kwargs)

    def make_sample(self, **kwargs):
        return self.make_qualitative_sample(**kwargs)
