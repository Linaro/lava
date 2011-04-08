"""
XMP-RPC API
"""

import xmlrpclib

class SchedulerAPI(object):
    """
    Scheduler API object.

    All public methods are automatically exposed as XML-RPC methods
    """

    def submit_job(self, user_name, job_name, timeout, priority, json_content):
        """
        Name
        ----
        `submit_job` (`user_name`, `job_name`, `timeout`, `priority`, `json_content`)

        Description
        -----------
        Submit a test job.

        Arguments
        ---------
        `user_name`: string
            User name.
        `job_name`: string
            Job name.
        `timeout`: integer
            Job timeout.
        `priority`: integer
            Job priority.
        `json_content`: string
            JSON defintion for the job.

        Return value
        ------------
        Return OK if submitted without errors.

        Exceptions raised
        -----------------
        TODO
        """
        pass

    def resubmit_job(self, job_id, user_name, timeout, priority):
        """
        Name
        ----
        `resubmit_job` (`job_id`, `user_name`, `timeout`, `priority`)

        Description
        -----------
        Resubmit a test job.

        Arguments
        ---------
        `job_id`: integer
            Job ID.
        `user_name`: string
            User name.
        `timeout`: integer
            Job timeout (optional).
        `priority`: integer
            Job priority (optional).
        
        Return value
        ------------
        Return OK if resubmitted without errors.

        Exceptions raised
        -----------------
        TODO
        """
        pass

    def cancel_job(self, job_id):
        """
        Name
        ----
        `cancel_job` (`job_id`)

        Description
        -----------
        Cancel a test job.

        Arguments
        ---------
        `job_id`: integer
            Job ID.
        
        Return value
        ------------
        Return OK if canceled without errors.

        Exceptions raised
        -----------------
        TODO
        """
        pass

    def get_result(self, job_id):
        """
        Name
        ----
        `get_result` (`job_id`)

        Description
        -----------
        Get result HTTP link for a finished test job.

        Arguments
        ---------
        `job_id`: integer
            Job ID.
        
        Return value
        ------------
        Return HTTP link.

        Exceptions raised
        -----------------
        TODO
        """
        pass

    def get_job_status(self, job_id):
        """
        Name
        ----
        `get_job_status` (`job_id`)

        Description
        -----------
        Get status of a test job.

        Arguments
        ---------
        `job_id`: integer
            Job ID.
        
        Return value
        ------------
        Return status.

        Exceptions raised
        -----------------
        TODO
        """
        pass

    def list_jobs(self, list_size, user_name):
        """
        Name
        ----
        `list_jobs` (`list_size`, `user_name`)

        Description
        -----------
        Get list of jobs for a specific user name.

        Arguments
        ---------
        `list_size`: integer
            List size.
        `user_name`: string
            User name (optional).
        
        Return value
        ------------
        Return job list for a specific user. If no user provided, return
        list with recent jobs from all users with max X number of jobs.

        Exceptions raised
        -----------------
        TODO
        """
        pass

