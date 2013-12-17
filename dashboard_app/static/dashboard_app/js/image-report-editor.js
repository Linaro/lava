select_filter = function() {
    // Open the filter select dialog.
    $('#filter_select_dialog').dialog('open');
}

filters_callback = function(id, name) {
    // Function which will be called when a filter is selected from the dialog.

    url = "/dashboard/filters/+get-tests-json";

    $.ajax({
        url: url,
        async: false,
        data: {"id": id},
        beforeSend: function () {
            $('#filter-container').remove();
            $('#filter_select_dialog').dialog('close');
            $('#loading_dialog').dialog('open');
        },
        success: function (data) {
            $('#loading_dialog').dialog('close');
            $("#id_filter").val(id);
            add_filter_container(data, id, name);
        },
        error: function(data, status, error) {
            $('#loading_dialog').dialog('close');
            alert('Filter could not be loaded, please try again.');
        }
    });
}

add_filter_container = function(data, filter_id, title) {
    // Adds elements which contain tests or test cases from the previously
    // selected filter.

    content = '<hr><div class="filter-title">' + title + '</div>';

    if ($('#id_chart_type').val() == "pass/fail") {
        test_label = "Tests";
    } else {
        test_label = "Test Cases";
    }

    if ($('#id_chart_type').val() == "measurement") {
        content += '<div id="test_select_container">' +
            '<select id="test_select">' +
            '<option value="">--Select Test--</option>';
        content += generate_test_options(data);
        content += '</select></div>';
    }

    content += '<div class="selector"><div class="selector-available"><h2>' +
        'Select ' + test_label + '</h2>';

    content += '<select id="available_tests" multiple class="filtered">';

    if ($('#id_chart_type').val() == "pass/fail") {
        content += generate_test_options(data);
    }

    content += '</select>';

    content += '<a id="add_all_link" href="javascript: void(0)">' +
        'Choose All</a>';
    content += '</div>';

    content += '<ul class="selector-chooser">' +
        '<li><a href="javascript: void(0)" id="add_link"' +
        'class="selector-add active"></a></li>' +
        '<li><a href="javascript: void(0)" id="remove_link"' +
        'class="selector-remove active"></a></li>' +
        '</ul>';

    content += '<div class="selector-chosen"><h2>' +
        'Choosen ' + test_label + '</h2>';

    content += '<select id="chosen_tests" onchange="toggle_alias()" multiple class="filtered"></select>';
    content += '<a id="remove_all_link" href="javascript: void(0)">' +
        'Remove All</a>';
    content += '</div></div>';

    content += '<div id="alias_container">Alias<br/>';
    content += '<input type="text" onkeyup="copy_alias(this);" id="alias" />';
    content += '</div>';

    $('<div id="filter-container"></div>').html(
        content).appendTo($('#filters_div'));

    update_events(filter_id);
}

generate_test_options = function(data, chart_type="pass/fail") {

    content = "";
    for (i in data) {
        if (chart_type == "pass/fail") {
            content += '<option value="' + data[i].pk + '">' +
                data[i].fields.test_id + '</option>';
        } else {
            content += '<option value="' + data[i].pk + '">' +
                data[i].fields.test_case_id + '</option>';
        }
    }

    return content;
}

update_events = function(filter_id) {
    // Add onclick events to the links controlling the select boxes.
    // Add on change event for test select on measurement reports.

    $('#add_link').click(function() {
        move_options('available_tests', 'chosen_tests');
    });
    $('#remove_link').click(function() {
        move_options('chosen_tests', 'available_tests');
    });
    $('#add_all_link').click(function() {
        $('#available_tests option').each(function() {
            $(this).attr('selected', 'selected');
        });
        move_options('available_tests', 'chosen_tests');
    });
    $('#remove_all_link').click(function() {
        $('#chosen_tests option').each(function() {
            $(this).attr('selected', 'selected');
        });
        move_options('chosen_tests', 'available_tests');
    });

    $('#test_select').change(function() {
       test_changed(filter_id, $(this).val());
    });
}

move_options = function(from_element, to_element) {
    var options = $("#" + from_element + " option:selected");
    $("#" + to_element).append(options.clone());
    $(options).remove();

    update_aliases();
    toggle_alias();
}

add_selected_options = function() {
    // Adds options from chosen tests select box as hidden fields.

    $('#chosen_tests option').each(function() {
        if ($('#id_chart_type').val() == "pass/fail") {
            field_name = "image_chart_tests";
        } else {
            field_name = "image_chart_test_cases";
        }
        $('<input type="hidden" name="' + field_name +
          '" value="'+ $(this).val() + '" />').appendTo($('#add_filter_link'));
    });
}

update_aliases = function() {
    // Update hidden aliases inputs based on chosen tests.

    $('#chosen_tests option').each(function() {
        if ($('#alias_' + $(this).val()).length == 0) {
            $('<input type="hidden" class="alias" data-sid="' + $(this).val() +
              '" name="aliases" id="alias_' + $(this).val() +
              '" />').appendTo($('#aliases_div'));
        }
    });
    chosen_tests = $.map($('#chosen_tests option'), function(e) {
        return e.value;
    });
    $('.alias').each(function(index, value) {
        test_id = value.id.split('_')[1];

        if (chosen_tests.indexOf(test_id) == -1) {
            $('#alias_' + test_id).remove();
        }
    });
}

toggle_alias = function() {
    // Show/hide alias input field.

    if ($('#chosen_tests option:selected').length == 1) {
        $('#alias_container').show();
        test_id = $('#chosen_tests option:selected').val();
        $('#alias').val($('#alias_' + test_id).val());
    } else {
        $('#alias_container').hide();
    }
}

copy_alias = function(e) {
    // Populate alias input based on the selected test.

    if ($('#chosen_tests option:selected').length == 1) {
        test_id = $('#chosen_tests option:selected').val();
        $('#alias_' + test_id).val(e.value);
    }
}

test_changed = function(filter_id, test_id) {
    // When the test in the drop down is changed, retrieve relevant test
    // cases for the available test cases select box.

    if (test_id) {
        url = "/dashboard/filters/+get-test-cases-json";

        $.ajax({
            url: url,
            async: false,
            data: {"id": filter_id, "test_id": test_id},
            beforeSend: function () {
                $('#loading_dialog').dialog('open');
                $("#available_tests option").remove();
            },
            success: function (data) {
                $('#loading_dialog').dialog('close');
                $("#available_tests").html(
                    generate_test_options(data, "measurement"));
            },
            error: function(data, status, error) {
                $('#loading_dialog').dialog('close');
                alert('Test run could not be loaded, please try again.');
            }
        });
    }
}

sort_aliases = function() {
    // Pre submit function. Sort the aliases hidden inputs.

    $('#aliases_div input').sort(function(a,b) {
        return parseInt(a.dataset.sid) > parseInt(b.dataset.sid);
    }).appendTo('#aliases_div');
}

init_filter_dialog = function() {
    // Setup the filter table dialog.

    var filter_dialog = $('<div id="filter_select_dialog"></div>');
    $('#all-filters_wrapper').wrapAll(filter_dialog);

    $('#filter_select_dialog').dialog({
        autoOpen: false,
        title: 'Select Filter',
        draggable: false,
        height: 550,
        width: 820,
        modal: true,
        resizable: false
    });
}

init_loading_dialog = function() {
    // Setup the loading image dialog.

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
