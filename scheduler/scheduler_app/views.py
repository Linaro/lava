from django.shortcuts import render_to_response
from scheduler_app.models import TestCase, TestJob
from scheduler_app.forms import TestJobForm

"""
Default JSON-formatted test job.
"""
default_test_job = {
  "job_name": "foo",
  "target": "panda01",
  "timeout": 18000,
  "actions": [
    {
      "command": "deploy_linaro_image",
      "parameters":
        {
          "rootfs": "",
          "hwpack": ""
        }
    },
    {
      "command": "boot_linaro_image"
    },
    {
      "command": "test_abrek",
      "parameters":
        {
          "test_name": "ltp"
        }
    },
    {
      "command": "submit_results",
      "parameters":
        {
          "server": "http://dashboard.linaro.org",
          "stream": "panda01-ltp"
        }
    }
  ]
}

def index(request):
    if request.method == 'POST':
        if request.is_ajax():
            test_suite_id = request.POST['test_suite']
            test_cases = TestCase.objects.filter(test_suite = test_suite_id)
            return render_to_response('scheduler/test_cases.html',
                {'test_cases': test_cases})

        # A form bound to the POST data
        form = TestJobForm(request.POST)

        # All validation rules pass
        if form.is_valid():
            test_job = form.save(commit = False)

            # Load the default JSON job data
            definition = default_test_job

            # Update job data with the form values - ugly, but works
            definition['job_name'] = form.cleaned_data['description']
            definition['actions'][0]['parameters']['rootfs'] = form.cleaned_data['rootfs']
            definition['actions'][0]['parameters']['hwpack'] = form.cleaned_data['hwpack']
            definition['target'] = form.cleaned_data['target'].hostname
            definition['timeout'] = form.cleaned_data['timeout']
            definition['actions'][2]['parameters']['test_name'] = request.POST['test_case']

            print definition #for testing purposes, remove in live env.

            test_job.status = TestJob.SUBMITTED
            test_job.definition = definition

            # Save job in the database
            test_job.save()
            # Display clean, unbound form, old form data not used
            form = TestJobForm()
    else:
        # No form posted, create an unbound empty form
        form = TestJobForm()

    # Show 10 latest submitted jobs
    job_list = TestJob.objects.all().order_by('-submit_time')[:10]

    return render_to_response('scheduler/index.html',
    {
        'form': form,
        'job_list': job_list,
    })
