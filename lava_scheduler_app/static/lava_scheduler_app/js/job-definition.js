create_tmp_element = function (text) {
    // create temporary textarea in order to copy it's contents.
    var tmp_element = $('<textarea />');
    tmp_element.css("fontSize", "12pt");
    tmp_element.css("border", "0");
    tmp_element.css("padding", "0");
    tmp_element.css("margin", "0");
    // Move element out of screen
    tmp_element.css("position", "absolute");
    tmp_element.css("left", "-9999px");
    var yPosition = window.pageYOffset || document.documentElement.scrollTop;
    tmp_element.on("focus", window.scrollTo(0, yPosition));
    tmp_element.css("top", yPosition + "px");

    tmp_element.attr("readonly", "");
    tmp_element.val(text);

    $("body").append(tmp_element);

    return tmp_element;
}

$(document).ready(
    function() {
        $("#copy_link").on("click", function() {

            tmp_element = create_tmp_element($("#job_definition_text").html());
            tmp_element.select();
            try {
                var success = document.execCommand('copy');
                if (!success) {
                    console.log('Copying job definition was unsuccessful');
                }
            } catch (error) {
                console.log(
                    'Not able to copy job definition to clipboard. ' + error);
            } finally {
                tmp_element.remove();
            }
        });
    }
);
