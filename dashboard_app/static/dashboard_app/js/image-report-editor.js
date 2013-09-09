$().ready(function () {

    init_filter_dialog();
    init_loading_dialog();
});

add_filter = function() {
    $('#filter_select_dialog').dialog('open');
}

filters_callback = function(id, name) {

    if ($('#id_chart_type').val() == "pass/fail") {
        url = "/dashboard/filters/+get-tests-json";
    } else {
        url = "/dashboard/filters/+get-test-cases-json";
    }

    $.ajax({
        url: url,
        data: {"id": id},
        beforeSend: function () {
            $('#filter_select_dialog').dialog('close');
            $('#loading_dialog').dialog('open');
        },
        success: function (data) {
            $('#loading_dialog').dialog('close');
            add_filter_container(data, id, name);
        },
        error: function(data, status, error) {
            $('#loading_dialog').dialog('close');
            //$('#left_div').html('<span class="error">Filter could not be loaded, please try again.</span>')
        }
    });
}

add_filter_container = function(data, filter_id, title) {

    content = '<hr><div class="filter-title">' + title + '</div>';

    if ($('#id_chart_type').val() == "pass/fail") {
        test_label = "Tests";
    } else {
        test_label = "Test Cases";
    }

    content += '<div class="selector"><div class="selector-available"><h2>' +
        'Select ' + test_label + '</h2>';

    content += '<select id="available_tests_' + filter_id +
        '" multiple class="filtered">';
    for (i in data) {
        content += '<option value="">' + data[i].fields.test_id + '</option>';
    }
    content += '</select>';

    content += '<a id="add_all_link_' + filter_id +
        '" href="javascript: void(0)">' +
        'Choose All</a>';
    content += '</div>';

    content += '<ul class="selector-chooser">' +
        '<li><a href="javascript: void(0)" id="add_link_' + filter_id + '" ' +
        'class="selector-add active"></a></li>' +
        '<li><a href="javascript: void(0)" id="remove_link_' + filter_id +
        '" class="selector-remove active"></a></li>' +
        '</ul>';

    content += '<div class="selector-chosen"><h2>' +
        'Choosen ' + test_label + '</h2>';

    content += '<select id="chosen_tests_' + filter_id +
        '" multiple class="filtered"></select>';
    content += '<a id="remove_all_link_' + filter_id +
        '" href="javascript: void(0)">Remove All</a>';
    content += '</div></div>';

    $('<div class="filter-container"></div>').html(
        content).appendTo($('#filters_div'));

    update_events(filter_id);
}

update_events = function(filter_id) {
    $('#add_link_' + filter_id).click(function() {
        move_options('available_tests_' + filter_id,
                     'chosen_tests_' + filter_id);
    });
    $("#remove_link_" + filter_id).click(function() {
        move_options('chosen_tests_' + filter_id,
                     'available_tests_' + filter_id);
    });
    $("#add_all_link_" + filter_id).click(function() {
        $('#available_tests_' + filter_id + ' option').each(function() {
            $(this).attr('selected', 'selected');
        });
        move_options('available_tests_' + filter_id,
                     'chosen_tests_' + filter_id);
    });
    $("#remove_all_link_" + filter_id).click(function() {
        $('#chosen_tests_' + filter_id + ' option').each(function() {
            $(this).attr('selected', 'selected');
        });
        move_options('chosen_tests_' + filter_id,
                     'available_tests_' + filter_id);
    });
}

move_options = function(from_element, to_element) {
    var options = $("#" + from_element + " option:selected");
    $("#" + to_element).append(options.clone());
    $(options).remove();
}

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

init_loading_dialog = function() {

    $('#loading_dialog').dialog({
        autoOpen: false,
        title: '',
        draggable: false,
        height: 35,
        width: 250,
        modal: true,
        resizable: false,
        dialogClass: 'loading-dialog'
    });

    $('.loading-dialog div.ui-dialog-titlebar').hide();
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