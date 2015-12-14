/* Polling support for pipeline jobs.

Ensure that these variables are defined in pages using this support.
 var job_status_url = {% url 'lava.scheduler.job_status' pk=job.pk %};
 var section_url = '{% url 'lava.scheduler.job_pipeline_sections' pk=job.pk %}'

For complete log support:
 var logs_url = '{% url 'lava.scheduler.job_pipeline_incremental' pk=job.pk %}{% querystring 'summary'=0 %}'
For summary support:
 var logs_url = '{% url 'lava.scheduler.job_pipeline_incremental' pk=job.pk %}{% querystring 'summary'=1 %}'
*/

var pollTimer = null;
var device = 1;
var job = 1;
var logs = 1;
var timing = 1;
var priority = 1;
var section_data = 1;

function isElementInViewport(el) {
    //special bonus for those using jQuery
    if (typeof jQuery === "function" && el instanceof jQuery) {
        el = el[0];
    }

    var rect = el.getBoundingClientRect();

    return rect.bottom > 0 &&
        rect.right > 0 &&
        rect.left < (window.innerWidth || $(window).width()) &&
        rect.top < (window.innerHeight || $(window).height());
}

function poll () {
    var el = $('#bottom');
    var scroll = isElementInViewport(el);
    $.ajaxSetup({
        dataType: 'html',
        global: false
    });
    if (job) {
    $.ajax({
        dataType: 'json',
    url: job_status_url,
    success: function (res_data, success, xhr) {
        var data = eval(res_data);
      $('#jobstatusdef').html(data['job_status']);
      $('#statusblock').html(data['device']);
      $('#jobtiming').html(data['timing']);
        if (!('priority' in data)) {
            $('#priority-choice').css('display', 'none')
        }
        if ('failure_comment' in data) {
          $('#failure_comment').html(data['failure_comment']);
          $('#failure_block').css('display', 'block');
        }
      if ('X-JobStatus' in data) {
        job = null;
      }
    }
  });
    }
    if (logs) {
    $.ajax({
        dataType: 'html',
    url: logs_url,
    success: function (data, success, xhr) {
      $('#log_data').html(data);
      if (xhr.getResponseHeader('X-Is-Finished')) {
        $('#log_progress').find('img').css('display', 'none');
          logs = null;
      } else {
          if (scroll) {
            document.getElementById('bottom').scrollIntoView();
          }
      }
    }
  });
  }
    if (section_data) {
    $.ajax({
        dataType: 'html',
    url: section_url,
    success: function (data, success, xhr) {
      $('#sectionlogs').html(data);
      if (xhr.getResponseHeader('X-Sections')) {
          section_data = null;
      }
    }
  });
  }
    if ((logs !== null) || (job !== null) || (section_data !== null)) {
        pollTimer = setTimeout(poll, 6000);
    }
}
$(document).ready(
function () {
pollTimer = setTimeout(poll, 6000);
}
);
