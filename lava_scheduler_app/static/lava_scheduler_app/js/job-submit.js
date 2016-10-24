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
                if (is_url($("#definition-input").val()) && $("#definition-input").val().split("\n").length == 1) {
                    load_url($("#definition-input").val());
                } else {
                    validate_input();
                }
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

load_url = function(url) {
    // Loads definition content if URL is provided in the text area.
    $.ajax({
        type: "POST",
        url: remote_definition_url,
        data: {
            "url": url.trim(),
            "csrfmiddlewaretoken": $("[name='csrfmiddlewaretoken']").val()
        },
        success: function(data) {
            try {
                $("#definition-input").val(data);
                validate_input();
            } catch (e) {
                validate_definition_callback(e);
                return;
            }
        }
    });
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
    if (result == "success") {
        $("#valid_container").html("Valid definition.");
        $("#valid_container").css("backgound-color", "#50ef53");
        $("#valid_container").css("color", "#139a16");
        $("#valid_container").css("border-color", "#139a16");
        $("#valid_container").show();
        $("#submit").removeAttr("disabled");
        $("#validation_note").hide();
        unselect_error_line();
    } else {
        $("#valid_container").html("Invalid definition: " + result);
        $("#valid_container").css("backgound-color", "#ff8383");
        $("#valid_container").css("color", "#da110a");
        $("#valid_container").css("border-color", "#da110a");
        $("#valid_container").show();
        $("#submit").attr("disabled", "disabled");
        $("#validation_note").hide();
        select_error_line(result);
    }
}

unselect_error_line = function() {
    // Unselect any potential previously selected lines.
    $(".lineno").removeClass("lineselect");
}

select_error_line = function(error) {
    // Selects the appropriate line in text area based on the parsed error msg.
    line_string = error.match(/line \d+/).toString();
    $(".lineno").removeClass("lineselect");

    if (line_string) {
        line_number = parseInt(line_string.split(" ")[1]);

        $("#lineno"+line_number).addClass("lineselect");

        // Scroll the textarea to the highlighted line.
        $("#definition-input").scrollTop(
            line_number * (parseInt($("#lineno1").css(
                "height")) - 1) - ($("#definition-input").height() / 2));
    }
}

is_url = function (str) {
    var regexp = /^(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/
    return regexp.test(str);
}
