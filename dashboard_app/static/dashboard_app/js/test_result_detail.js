$(document).ready(function () {

    init_comments_dialog = function () {
        $('#comments_edit_dialog').dialog({
            autoOpen: false,
            title: 'Edit comments',
            draggable: false,
            height: 280,
            width: 420,
            modal: true,
            resizable: false
        });
    }

    open_comments_dialog = function() {
        $('#comments_edit_dialog').dialog('open');
    }

    comments_dialog_callback = function() {

        url_addition = "";
        if (window.location.pathname[
            window.location.pathname.length-1] != "/") {
            url_addition = "/";
        }
        url = window.location.pathname + url_addition + "+update-comments";

        $.ajax({
            url: url,
            type: "POST",
            data: {
                csrfmiddlewaretoken: csrf_token,
                comments: $("#comments_text").val(),
            },
            success: function (data) {
                $('#comments_edit_dialog').dialog('close');
                $('#comments_container').html(
                    data[0].fields.comments.replace(/\n/g, "<br/>"));
            },
        });
    }

    init_comments_dialog();
});
