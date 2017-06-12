To rebuild and update a pipeline reference, use:

    import yaml
    with open('/tmp/test.yaml', 'w') as describe:
        yaml.dump(self.job.pipeline.describe(False), describe)

(Avoid opening in binary mode as this would fail with python3.)

Then use:

from lava_dispatcher.pipeline.test.test_basic import pipeline_reference

    # Check Pipeline
    description_ref = self.pipeline_reference('kexec.yaml')
    self.assertEqual(description_ref, self.job.pipeline.describe(False))

or just

    self.assertEqual(self.pipeline_reference(filename), self.job.pipeline.describe(False))

The name of the pipeline_ref file should match the name of the equivalent file in sample_jobs.

To change multiple pipeline references at the same time, change
self.update_ref to True in test_basic.StdoutTestCase - always check all changes to
the pipeline reference files *carefully* before sending for review.
