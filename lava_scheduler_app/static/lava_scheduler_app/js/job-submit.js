$(window).ready(
    function () {
        $("#json-input").linedtextarea();

        $("#json-input").bind('paste', function() {
            // Need a timeout since paste event does not give the content
            // of the clipboard.
            setTimeout(function(){
                validate_job_data($("#json-input").val());
            },100);
        });

        $("#json-input").blur(function() {
            validate_job_data($("#json-input").val());
        });
    });

validate_job_data = function() {
    $.post(window.location.pathname,
           {"json-input": json_input,
            "csrfmiddlewaretoken": $("[name='csrfmiddlewaretoken']").val()},
           function(data) {

           });
}
