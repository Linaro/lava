$("#validate").click(function(){
    $("#busyIndicator").show(); 
    validate_input();
    $("#busyIndicator").hide(); 
});

$(document).ajaxStart(function () {
    $('#busyIndicator').show();
}).ajaxStop(function () {
    $('#busyIndicator').hide();
});

$(window).ready(
    function () {
        $("#definition-input").linedtextarea();

        $("#definition-input").bind('paste', function() {
            // Need a timeout since paste event does not give the content
            // of the clipboard.
            setTimeout(function(){
              validate_input();
            },100);
        });

        $("#definition-input").keypress(function() {
            $("#submit").attr("disabled", "disabled");
            $("#valid_container").hide();
            $("#validation_note").show();
         });

        $("#submit").attr("disabled", "disabled");
        $("#validation_note").hide();

        // For resubmit purposes only.
        validate_input();
    });

validate_input = function() {
    if ($("#definition-input").val() != "") {
        validate_job_definition($("#definition-input").val());
    }
}

validate_job_definition = function(data) {
    $.post(window.location.pathname,
           {"definition-input": data,
            "csrfmiddlewaretoken": $("[name='csrfmiddlewaretoken']").val()},
           function(data) {
               validate_definition_callback(data);
           }, "json");
}

validate_definition_callback = function(result) {
    // Updates the css of the definition validation container with
    // appropriate msg.
    if (result["result"] == "success") {
        if(result["warnings"]) {
            $("#valid_container").html("Valid definition with warnings: " + result["warnings"]);
            $("#valid_container").css("color", "#ec971f");
            $("#valid_container").css("border-color", "#d58512");
        } else {
            $("#valid_container").html("Valid definition.");
            $("#valid_container").css("color", "#5cb85c");
            $("#valid_container").css("border-color", "#4cae4c");
        }
        $("#valid_container").show();
        $("#submit").removeAttr("disabled");
        $("#validation_note").hide();
        unselect_error_line();
    } else {
        $("#valid_container").html("Invalid definition: " + result["errors"]);
        $("#valid_container").css("color", "#d9534f");
        $("#valid_container").css("border-color", "#d43f3a");
        $("#valid_container").show();
        $("#submit").attr("disabled", "disabled");
        $("#validation_note").hide();
        select_error_line(result["errors"]);
    }
}

unselect_error_line = function() {
    // Deselect any potential previously selected lines.
    $(".lineno").removeClass("lineselect");
}

select_error_line = function(error) {
    // Selects the appropriate line in text area based on the parsed error msg.
    line_string = error.match(/line \d+/);
    if (line_string) {
        line_string = line_string.toString();
        $(".lineno").removeClass("lineselect");

        line_number = parseInt(line_string.split(" ")[1]);
        $("#lineno"+line_number).addClass("lineselect");

        // Scroll the textarea to the highlighted line.
        $("#definition-input").scrollTop(
            line_number * (parseInt($("#lineno1").css(
                "height")) - 1) - ($("#definition-input").height() / 2));
    }
}
