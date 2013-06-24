$(window).ready(
    function () {
        $("#json-input").linedtextarea();

        // Need to change this because our text area field is resizable.
        $("#lava-footer").css("position", "relative");
        $("#lava-footer-sanitizer").css("padding-bottom", "0px");
    });
