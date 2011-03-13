from django.shortcuts import render_to_response
from scheduler_app.models import Device, Test, TestJob, TestJobForm
import json

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
          "rootfs": "http://snapshots.linaro.org/11.05-daily/linaro-developer/20110208/0/images/tar/linaro-n-developer-tar-20110208-0.tar.gz",
          "hwpack": "http://snapshots.linaro.org/11.05-daily/linaro-hwpacks/panda/20110208/0/images/hwpack/hwpack_linaro-panda_20110208-0_armel_supported.tar.gz"
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
    if request.method == 'POST': # If a test job has been submitted...
        form = TestJobForm(request.POST) # A form bound to the POST data
        
        if form.is_valid(): # All validation rules pass
            test_job = form.save(commit=False)
            
            # Load the default JSON job data
            raw_test_job = default_test_job

            # Update job data with the form values - ugly, but works
            raw_test_job['job_name'] = form.cleaned_data['job_name']
            raw_test_job['actions'][0]['parameters']['rootfs'] = form.cleaned_data['rootfs']
            raw_test_job['actions'][0]['parameters']['hwpack'] = form.cleaned_data['hwpack']
            raw_test_job['target'] = form.cleaned_data['target'].device_name
            raw_test_job['timeout'] = form.cleaned_data['timeout']
            raw_test_job['actions'][2]['parameters']['test_name'] = form.cleaned_data['tests'].test_name

            print raw_test_job #for testing purposes, remove in live env.

            test_job.status = "SUBMITTED"
            test_job.raw_test_job = raw_test_job

            test_job.save()            
    else:
        # No form posted, create an unbound empty form
        form = TestJobForm()
    
    # Show 10 latest submitted jobs
    job_list = TestJob.objects.all().order_by('-submit_time')[:10]

    return render_to_response('scheduler/index.html', {
        'form': form,
        'job_list': job_list,
    })
