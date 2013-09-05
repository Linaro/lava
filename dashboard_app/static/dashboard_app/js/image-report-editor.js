$().ready(function () {

    init_filter_dialog();
    $('#filter_select_dialog').dialog('open');
//    $('#lava_tests_1_link').click(function () {
//        populate_dialog();
//        $('#filter_select_dialog').dialog('open');
//    });
});

init_filter_dialog = function() {

    var filter_dialog = $('<div id="filter_select_dialog"></div>');
    $('#all-filters_wrapper').wrapAll(filter_dialog);

    $('#filter_select_dialog').dialog({
        autoOpen: false,
        title: 'Select Filter',
        draggable: false,
        height: 280,
        width: 420,
        modal: true,
        resizable: false
    });
}

populate_dialog = function () {

    $.get('/lava/select/', function (data) {

        $('#lava_select_dialog').html(data);
        get_lava_tests_list();
    });
}

get_filters_list = function () {

    $.ajax({
        url: "/dashboard/filters/+search-json",
        data: {"term": ""},
        beforeSend: function () {
            // Do not show the select element if it is empty, just show the
            // spinner.
            //$('#available').hide();
        },
        success: function (data) {
            //$(data).prependTo($('#available'));
            //$('#available').show();
            //set_callbacks();
            //toggle_existing_options();
            alert(data);
        },
        error: function(data, status, error) {
            //$('#left_div').html('<span class="error"><strong>Oops!</strong> The LAVA server is not responding.</span>')
        }
    });

}

set_callbacks = function () {

    $('#loading_div').show().ajaxStop(function () {
        // Disable the spinner once AJAX is done.
        $(this).hide();
    });
    $('#add_button').click(function () {
        return !$('#available option:selected').remove().appendTo('#chosen');
    });
    $('#remove_button').click(function () {
        return !$('#chosen option:selected').remove().appendTo('#available');
    });
    $('#id_select_button').click(function () {
        var values = "";
        $("#chosen > option").each(function() {
            // We store the values as a semi-colon separated list of names.
            values += $(this).val() + ";";
        });
        $('#id_lava_tests_0').val(values);
        // Ellipsize the visual representation if it exceeds a prefixed amount
        // of chars in length, and append an ellipsis.
        if (values.length > 30) {
            values = values.substring(0, 27) + "&#8230;";
        }
        $('#lava_tests_1_link').html(values);
        $('#lava_select_dialog').dialog('close');
    });
}

toggle_existing_options = function () {
    var lava_tests_array = $("#id_lava_tests_0").val().split(";");
    for (var i in lava_tests_array) {
        // Add options to the 'chosen' select field.
        var lava_test = lava_tests_array[i];
        if (lava_test != "") {
            var select_option = new Option(lava_test,
                                           lava_test, true, true);
            select_option.setAttribute("id", "id_" + lava_test);
            $("#chosen").append(select_option);
        }
        // Remove options from the 'available' select field.
        $("#available option[value=" + lava_test + "]").remove();
    }
}