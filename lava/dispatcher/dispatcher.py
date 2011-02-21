

class JobDispatcher(object):
    
    def dispatch_job(self, driver, job):
        """
        Dispatches specified job on the specified device driver.

        The driver must be instantiated before to separate the dispatcher
        from database/django layer.

        The job must be a Job instance, it must be previously loaded from JSON.
        """
        raise NotImplementedError()

