See also:
https://staging.validation.linaro.org/static/docs/v2/dispatcher-testing.html#lava-dispatcher
or http://localhost/static/docs/v2/dispatcher-testing.html#lava-dispatcher

To rebuild and update a pipeline reference, use:

    import yaml
    with open('/tmp/test.yaml', 'w') as describe:
        yaml.dump(self.job.pipeline.describe(), describe)

(Avoid opening in binary mode as this would fail with python3.)

Then use:

from tests.lava_dispatcher.test_basic import pipeline_reference

    # Check Pipeline
    description_ref = self.pipeline_reference('kexec.yaml')
    self.assertEqual(description_ref, self.job.pipeline.describe())

or just

    self.assertEqual(self.pipeline_reference(filename), self.job.pipeline.describe())

The name of the pipeline_ref file should match the name of the equivalent file in sample_jobs.

To change multiple pipeline references at the same time, change
self.update_ref to True in test_basic.StdoutTestCase - always check all changes to
the pipeline reference files *carefully* before sending for review.

Once you have a new unit test function with the pipeline_reference check in place,
the pipeline_reference can be updated by adding a temporary line:

    self.update_ref = True

Re-run the unit test and remove the line. Check that the diff for the pipeline
reference is sane before submitting for review.

For an example of a short unit test using a pipeline_reference, see:
tests/lava_dispatcher/test_uboot.py  - def test_transfer_media(self):
