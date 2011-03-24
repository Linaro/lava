"""
Module containing Scheduler handlers.
"""

class LavaDatabaseHandler(object):
    """
    LavaDatabaseHandler, base class for handling database in Lava
    Validation Scheduler

    Constructor:
    @param

    @return: none
    """

    def __init__(self):
        pass

    def save_test_job(self, test_job):
        pass

    def get_job_status(self, job_id):
        pass

    def update_job_status(self, job_id, status):
        pass

    def get_raw_job(self, job_id):
        pass

    def get_job_priority(self, job_id):
        pass


