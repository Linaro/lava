$(document).ready(function() {
    isValidUrl = function(url) {
        return url.match(/^https?:\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>\#%"\,\{\}\\|\\\^\[\]`]+)?$/);
    }

    $(".buglink").on("click", function() {
        object_id = $(this).attr("id").split("_")[1];
        $.ajax({
            url: bug_links_url,
            type: 'POST',
            data: {
                csrfmiddlewaretoken: csrf_token,
                content_type_id: content_type_id,
                object_id: object_id
            },
            beforeSend: function () {
                $('#refresh_loading_dialog').show();
            },
            success: function(data, textStatus, jqXHR){
		$('#refresh_loading_dialog').hide();
                $("#existing_bug_links").html("");
                if (data.length == 0) {
                    $("#existing_bug_links").html(
                        "No bugs linked at this time.");
                }
                for (index in data) {
                    if (data[index].fields.url.length > 60) {
                        bug_link_url = data[index].fields.url.substring(0,60) +
                            '...';
                    } else {
                        bug_link_url = data[index].fields.url;
                    }

                    $("#existing_bug_links").append(
                        '<div class="row">' +
                            '<div class="col-md-10">' +
                            '<a href="' + data[index].fields.url +
                            '" target="_blank">' +
                            bug_link_url +
                            '</a>' +
                            '</div>' +
                            '<div class="col-xs-2">' +
                            '<a class="glyphicon glyphicon-remove unlink-bug"' +
                            ' href="#" data-id="' + data[index].pk +
                            '" class="btn btn-danger"></a>' +
                            '</div>' +
                            '</div>');
                }

                $(".unlink-bug").on("click", function() {
                    $.ajax({
                        url: delete_bug_url,
                        type: 'POST',
	                data: {
                            csrfmiddlewaretoken: csrf_token,
                            bug_link_id: $(this).attr("data-id")
                        },
                        success: function(data, textStatus, jqXHR){
                            location.reload();
                        },
	                error: function(data, status, error) {
                            alert('Operation failed, please try again or contact system administrator.');
                        }
                    });
                });

                $("#id_object").val(object_id);
                $("#id_content_type").val(content_type_id);
                $("#id_url").val("");
                $("#bug_link_modal").modal("show");
            },
	    error: function(data, status, error) {
                $('#refresh_loading_dialog').hide();
                alert('Operation failed, please try again or contact system administrator.');
            }
        });
    });

    $("#submit_bug_link").on("click", function() {
        $.ajax({
            url: $("#bug_link_form").attr("action"),
            type: 'POST',
	    data: {
                csrfmiddlewaretoken: csrf_token,
                url: $("#id_url").val(),
                content_type_id: $("#id_content_type").val(),
                object_id: $("#id_object").val()
            },
	    beforeSend: function () {
                if (!isValidUrl($("#id_url").val())) {
                    alert("'" + $("#id_url").val() + "' is not a valid url.");
                    return false;
                }
            },
            success: function(data, textStatus, jqXHR){
		if (data[0] == true) {
                    location.reload();
                } else {
                    error_msg = "";
                    if (data[1] == "duplicate") {
                        error_msg = "This bug link for particular record already exists";
                    } else {
                        error_msg = "Incorrect data. Please try again."
                    }
                    $("#bug_link_errors").append(
                        "<div>" + error_msg + "</div>");
		}
            },
	    error: function(data, status, error) {
                alert('Operation failed, please try again or contact system administrator.');
            }
        });

    });
});
