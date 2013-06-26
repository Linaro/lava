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

        $("#submit").attr("disabled", "disabled");
    });

validate_job_data = function(json_input) {
    $.post(window.location.pathname,
           {"json-input": json_input,
            "csrfmiddlewaretoken": $("[name='csrfmiddlewaretoken']").val()},
           function(data) {
               if (data == "success") {
                   $("#json-valid-container").html("Valid JSON.");
                   valid_json_css(true);
                   $("#submit").removeAttr("disabled");
                   unselect_error_line();
               } else {
                   $("#json-valid-container").html(
                       data.replace("[u'", "").replace("']", ""));
                   valid_json_css(false);
                   $("#submit").attr("disabled", "disabled");
                   select_error_line(data);
               }
           }, "json");
}

valid_json_css = function (success) {
    // Updates the css of the json validation container with appropriate msg.
    if (success) {
        $("#json-valid-container").css("backgound-color", "#50ef53");
        $("#json-valid-container").css("color", "#139a16");
        $("#json-valid-container").css("border-color", "#139a16");
        $("#json-valid-container").show();
    } else {
        $("#json-valid-container").css("backgound-color", "#ff8383");
        $("#json-valid-container").css("color", "#da110a");
        $("#json-valid-container").css("border-color", "#da110a");
        $("#json-valid-container").show();
    }
}

unselect_error_line = function() {
    // Unselect any potential previously selected lines.
    $(".lineno").removeClass("lineselect");
}

select_error_line = function(error) {
    // Selects the appropriate line in text area based on the parsed error msg.
    line_string = error.split(": ")[1];
    line_number = parseInt(line_string.split(" ")[1]);

    $(".lineno").removeClass("lineselect");
    $("#lineno"+line_number).addClass("lineselect");

    // Scroll the textarea to the highlighted line.
    $("#json-input").scrollTop(
        line_number * parseInt($("#lineno1").css("height")));
}
