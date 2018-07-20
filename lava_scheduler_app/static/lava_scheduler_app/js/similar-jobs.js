$(document).ready(function () {

    var options_count = 0;
    add_option_row = function() {
        $("#options_container").append(
            "<div class='row' id='container_" + options_count + "'>" +
                "<div class='col-xs-4'>" +
                "<select id='table_" + options_count +
                "' name='table' >" +
                "</select></div>" +
                "<div class='col-xs-4'>" +
                "<div class='typeahead__container'>" +
                "<div class='typeahead__field'>" +
                "<div class='typeahead__query'><input type='search'" +
                " placeholder='Search' autocomplete='off' id='field_" +
                options_count + "' name='field' />" +
                "</div></div></div></div>" +
                "<div class='col-xs-4'>" +
                "<a class='glyphicon glyphicon-remove' href='#' id='remove_" +
                options_count + "' class='btn btn-danger'>" +
                "</a>" +
                "</div></div>");

        $.each(content_types, function(key, value) {
            $("#table_" + options_count).append(new Option(value, key));
        });
        $("#table_" + options_count + " option:contains(testjob)").prop(
            'selected', 'selected');
        $("#remove_" + options_count).click(function() {
            if (options_count == 1) {
                return false;
            }
            $(this).parent().parent().remove();
            options_count --;
        });
        $("#table_" + options_count).on(
            "change", {table_obj: $("#table_" + options_count)},
            table_changed);
        $("#table_" + options_count).trigger("change");

        options_count ++;
    }

    table_changed = function(event) {
        // Table field change callback.
        table_obj = event.data.table_obj;
        var elem_id = table_obj.attr("id").split("_")[1];
        field_obj = $("#field_" + elem_id);
        field_obj.val("");
        if (($("#similar_jobs_modal").data('bs.modal') || {}).isShown) {
            field_obj.typeahead({
                source: {
                    data: Object.keys(condition_choices[table_obj.val()]["fields"])
                },
                order: "asc",
                minLength: 1,
            });
        }
    }

    add_option_row();
    $("#submit_similar_jobs").on("click", function() {
        $("#similar_jobs_form").submit();
    });
});
