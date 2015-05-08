$(document).ready(function () {

    $.fn.editable.defaults.send = "always";

    trailing_slash = function() {
        if (window.location.pathname[
            window.location.pathname.length-1] != "/") {
            return "/";
        }
        return "";
    }


    remove_attribute_row = function(elem) {

        elem.parent().parent().prev().remove();
        elem.parent().parent().remove();
        // Check if container is empty.
        if (! $("#attributes_container :first-child").length) {
            $("#attributes_container").append('<i>none</i>');
        }
    }

    set_attribute_events = function() {

        $(".attribute-remove").click(function() {

            var url = window.location.pathname + trailing_slash() +
                remove_attribute_url;

            if ($(this).attr("data-pk")) {
                $.ajax({
                    url: url,
                    type: "POST",
                    data: {
                        'csrfmiddlewaretoken': csrf_token,
                        'pk': $(this).attr("data-pk"),
                    },
                    success: function (data) {
                        remove_attribute_row($("button[data-pk='" + data + "']"));
                    },
                    error: function() {
                        alert("Not able to remove attribute.");
                    },
                });
            } else {
                remove_attribute_row($(this));
            }
        });

        var update_url = window.location.pathname + trailing_slash() +
            update_attribute_url;

        $(".editable").editable(
            {
                url: update_url,
                params: function (params) {

                    // for updating existing use PK param (add to div as attr).
                    // ensure that name is always the key from form and value always the right one.
                    params.csrfmiddlewaretoken = csrf_token;
                    if ($(this).attr("data-name") == "name") {
                        params.name = params.value;
                        params.value = $(this).parent().next().children(":first").html();
                    } else { // $(this).attr("data-name") == "value"
                        params.name = $(this).parent().prev().children(":first").html();
                        // params.value remains unchanged.
                    }
                    params.pk = $(this).attr("data-pk");
                    return params;
                },
                ajaxOptions: {
                    type: 'post',
                    dataType: 'json'
                },
                success: function(data) {
                    $(this).attr("data-pk", data[0].pk);
                    if ($(this).attr("data-name") == "name") {
                        $(this).parent().next().children(":first").attr("data-pk", data[0].pk);
                        $(this).parent().next().children(":last").children(":first").attr("data-pk", data[0].pk);
                    } else { // $(this).attr("data-name") == "value"
                        $(this).parent().prev().children(":first").attr("data-pk", data[0].pk);
                        $(this).parent().children(":last").children(":first").attr("data-pk", data[0].pk);
                    }
                },
                error: function() {
                   alert("Not able to update custom attribute. Possible duplicate attribute name.");
                }
            }
        );
    }

    $("#attribute_insert").click(function() {
        // Check if first child tag is 'i', meaning the list is empty.
        if ($("#attributes_container :first-child").prop("tagName").toLowerCase() == "i") {
            // Remove the 'none' string.
            $("#attributes_container").html("");
        }
        $("#attributes_container").append(
            '<dt><div class="editable pull-right" data-pk="" data-name="name">attribute</div></dt>' +
            '<dd><div class="editable pull-left" data-pk="" data-name="value">value</div>' +
            '<div class="text-right"><button class="btn btn-xs btn-danger attribute-remove">' +
            '<span class="glyphicon glyphicon-remove"></span>' +
            '</button></div></dd>');

        set_attribute_events();
    });

    set_attribute_events();
});
