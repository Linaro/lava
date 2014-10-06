beautify_options = {
    "brace_style": "expand"
}

$("#validate").click(function(){
    $("#busyIndicator").show(); 
    validate_input($("#json-input").val());
    $("#busyIndicator").hide(); 
});

$(document).ajaxStart(function () {
    $('#busyIndicator').show();
}).ajaxStop(function () {
    $('#busyIndicator').hide();
});

$(window).ready(
    function () {
        $("#json-input").linedtextarea();

        $("#json-input").bind('paste', function() {
            // Need a timeout since paste event does not give the content
            // of the clipboard.
            setTimeout(function(){
                validate_input($("#json-input").val());
            },100);
        });

        $("#json-input").keypress(function() {
            $("#submit").attr("disabled", "disabled");
            $("#json-valid-container").hide();
            $("#validation_note").show();
         });

        $("#submit").attr("disabled", "disabled");
        $("#validation_note").hide();

        validate_input($("#json-input").val());
    });

validate_input = function(json_input) {

    if ($("#json-input").val() != "") {
        if (is_url($("#json-input").val().split("\n"))) {
            load_url();
        } else {
            $("#json-input").val(js_beautify(json_input, beautify_options));
            validate_job_data(json_input);
        }
    }
}

load_url = function() {
    // Loads JSON content if URL is provided in the json text area.
    if ($("#json-input").val().split("\n").length == 1) {
        $.ajax({
            type: "POST",
            url: remote_json_url,
            data: {
                "url": $("#json-input").val().trim(),
                "csrfmiddlewaretoken": $("[name='csrfmiddlewaretoken']").val()
            },
            success: function(data) {
                try {
                    $.parseJSON(data);
                    $("#json-input").val(js_beautify(data, beautify_options));
                    validate_job_data(data);
                } catch (e) {
                    $("#json-valid-container").html("Invalid JSON: " + data);
                    valid_json_css(false);
                    $("#submit").attr("disabled", "disabled");
                    $("#validation_note").show();
                }
            }});
    }
}

validate_job_data = function(data) {
    $.post(window.location.pathname,
           {"json-input": data,
            "csrfmiddlewaretoken": $("[name='csrfmiddlewaretoken']").val()},
           function(data) {
               if (data == "success") {
                   $("#json-valid-container").html("Valid JSON.");
                   valid_json_css(true);
                   $("#submit").removeAttr("disabled");
                   $("#validation_note").hide();
                   unselect_error_line();
               } else {
                   $("#json-valid-container").html(
                       data.replace("[u'", "").replace("']", "").
                           replace('[u"', "").replace('"]', ""));
                   valid_json_css(false);
                   $("#submit").attr("disabled", "disabled");
                   $("#validation_note").show();
                   select_error_line(data);
               }
           }, "json");
}

valid_json_css = function(success) {
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
        line_number * (parseInt($("#lineno1").css(
            "height")) - 1) - ($("#json-input").height() / 2));
}

is_url = function (str) {
    var regexp = /^(ftp|http|https):\/\/(\w+:{0,1}\w*@)?(\S+)(:[0-9]+)?(\/|\/([\w#!:.?+=&%@!\-\/]))?/
    return regexp.test(str);
}
