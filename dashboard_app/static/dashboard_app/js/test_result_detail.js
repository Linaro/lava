$(document).ready(function () {

    trailing_slash = function() {
        if (window.location.pathname[
            window.location.pathname.length-1] != "/") {
            return "/";
        }
        return "";
    }

    $('#saveCommentBtn').click(function(e) {
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

    $('#saveUnitsBtn').click(function(e) {
        if (!window.confirm("This action will change units systemwide for test case: " + test_case_name + ". Are you sure you want to proceed?")) {
            return false;
        }
        var units = $('#units_edit').val();
        var url = window.location.pathname + trailing_slash() +
            "+update-units";

        $.ajax({
            url: url,
            type: "POST",
            data: {
                'csrfmiddlewaretoken': csrf_token,
                'units': units,
            },
            success: function (data) {
                $('#unitsModal').modal('hide');
                $('#units').html(data[0].fields.units);
            },
        });
    });
});
