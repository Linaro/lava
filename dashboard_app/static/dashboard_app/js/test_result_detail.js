$(document).ready(function () {

    trailing_slash = function() {
        if (window.location.pathname[
            window.location.pathname.length-1] != "/") {
            return "/";
        }
        return "";
    }

    $('#saveBtn').click(function(e) {
        var comments = $('#comments_text').val();
        var url = window.location.pathname + trailing_slash() +
            "+update-comments";

        $.ajax({
            url: url,
            type: "POST",
            data: {
                'csrfmiddlewaretoken': csrf_token,
                'comments': comments,
            },
            success: function (data) {
                $('#commentModal').modal('hide');
                $('#comments_container').html(
                    data[0].fields.comments.replace(/\n/g, "<br/>"));
            },
        });
    });
});
