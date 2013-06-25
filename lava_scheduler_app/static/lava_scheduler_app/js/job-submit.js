$(window).ready(
    function () {
        $("#json-input").linedtextarea();

        $("#json-input").bind('paste', function() {
            alert("paste");
        });

        $("#json-input").blur(function() {
            alert("blur");
        });
    });
