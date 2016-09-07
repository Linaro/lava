filter_select_callback = function(filter_item, chart_id) {
    $("#id_filter").val(filter_item.id);
    filters_callback(chart_id, filter_item.id, filter_item.name);
    $(".ui-autocomplete-input").blur();
}

filters_callback = function(chart_id, filter_id, name) {
    // Function which will be called when a filter is selected.

    url = "/dashboard/image-charts/+filter-type-check";
    do_break = false;

    $.ajax({
        url: url,
        type: "POST",
        data: {
            csrfmiddlewaretoken: csrf_token,
            chart_id: chart_id,
            filter_id: filter_id
        },
        beforeSend: function () {
            $('#loading_dialog').dialog('open');
        },
        success: function (data) {
            $('#loading_dialog').dialog('close');
            if (data.result == "False") {
                alert('You must select filter with the same type' +
                      '(date/build numbers).');
                do_break = true;
            }
        },
        error: function(data, status, error) {
            $('#loading_dialog').dialog('close');
            alert('Filter could not be loaded, please try again.');
        }
    });

    if (do_break) {
        return;
    }

    url = "/dashboard/filters/+get-tests-json";

    $.ajax({
        url: url,
        data: {"id": filter_id},
        beforeSend: function () {
            $('#filter-container').remove();
            $('#loading_dialog').dialog('open');
        },
        success: function (data) {
            $('#loading_dialog').dialog('close');
            $("#id_filter").val(filter_id);
            add_filter_container(data, filter_id, name);
            filter_loaded_callback();

            if ($("#id_is_all_tests_included").prop("checked") == true) {
                $("#filter-container").hide();
            } else {
                $("#filter-container").show();
            }
        },
        error: function(data, status, error) {
            $('#loading_dialog').dialog('close');
            alert('Filter could not be loaded, please try again.');
        }
    });
}

filter_loaded_callback = function() {

    if ($('#id_chart_type').val() != "measurement") {
        for (i in selected_test_ids) {
            $('#available_tests option[value="' + selected_test_ids[i] + '"]').attr('selected', 'selected');
        }
        move_options('available_tests', 'chosen_tests');
    } else {
        for (i in selected_testcase_ids) {
            $('#chosen_tests').append($('<option>', {
                value: selected_testcase_ids[i].value,
                text: selected_testcase_ids[i].text
            }));
        }
    }
}


add_filter_container = function(data, filter_id, title) {
    // Adds elements which contain tests or test cases from the previously
    // selected filter.

    content = '<hr><div class="filter-title">' + title + '</div>';

    if ($('#id_chart_type').val() != "measurement") {
        test_label = "Tests";
    } else {
        test_label = "Test Cases";
    }

    if ($('#id_chart_type').val() == "measurement") {
        content += '<div id="test_select_container">' +
            '<select id="test_select">' +
            '<option value="">--Select Test--</option>';
        content += generate_test_options(data, "pass/fail");
        content += '</select></div>';
    }

    content += '<div class="selector"><div class="selector-available"><h2>' +
        'Select ' + test_label + '</h2>';


    content += '<p id="tests_filter" class="selector-filter">' +
        '<label for="tests_input">' +
        '<img class="help-tooltip"' +
        'src="/static/admin/img/selector-search.gif" alt=""></img>' +
        '</label>' +
        '<input id="tests_input" type="text"' +
        'placeholder="Filter"></input></p>';

    content += '<select id="available_tests" multiple class="filtered">';

    if ($('#id_chart_type').val() != "measurement") {
        content += generate_test_options(data, "pass/fail");
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

    content += '<select id="chosen_tests" multiple class="filtered"></select>';
    content += '<a id="remove_all_link" href="javascript: void(0)">' +
        'Remove All</a>';
    content += '</div></div>';

    $('<div id="filter-container"></div>').html(
        content).appendTo($('#filters_div'));

    update_events(filter_id);
}

generate_test_options = function(data, chart_type) {

    content = "";
    for (i in data) {
        if (chart_type != "measurement") {
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
       test_changed($(this).val());
    });

    $('#tests_input').keyup(function() {
       filter_available_tests($(this).val());
    });
}

filter_available_tests = function(text) {
    if (text != '') {
        $('#available_tests option').filter(function() {
            return !$(this).text().toLowerCase().startsWith(text);
        }).css("display", "none");
        $('#available_tests option').filter(function() {
            return $(this).text().toLowerCase().startsWith(text);
        }).css("display", "block");
    } else {
        $('#available_tests option').css("display", "block");
    }
}

move_options = function(from_element, to_element) {
    var options = $("#" + from_element + " option:selected");
    $("#" + to_element).append(options.clone());
    $(options).remove();
}

add_selected_options = function() {
    // Adds options from chosen tests select box as hidden fields.

    $('#chosen_tests option').each(function() {
        if ($('#id_chart_type').val() != "measurement") {
            field_name = "image_chart_tests";
        } else {
            field_name = "image_chart_test_cases";
        }
        $('<input type="hidden" name="' + field_name +
          '" value="'+ $(this).val() + '" />').appendTo($('#add_filter_link'));
    });
}

test_changed = function(test_id) {
    // When the test in the drop down is changed, retrieve relevant test
    // cases for the available test cases select box.

    if (test_id) {
        url = "/dashboard/filters/+get-test-cases-json";

        $.ajax({
            url: url,
            data: {"test_id": test_id},
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

init_loading_dialog = function() {
    // Setup the loading image dialog.

    $('#loading_dialog').dialog({
        autoOpen: false,
        title: '',
        draggable: false,
        height: 45,
        width: 260,
        modal: true,
        resizable: false,
        dialogClass: 'loading-dialog'
    });

    $('.loading-dialog div.ui-dialog-titlebar').hide();
}

init_test_edit_dialog = function() {
    // Setup the test edit dialog.
    $('#test_edit_dialog').dialog({
        autoOpen: false,
        title: '',
        draggable: false,
        height: 380,
        width: 480,
        modal: true,
        resizable: false,
        dialogClass: 'edit-dialog'
    });

    $('.edit-dialog div.ui-dialog-titlebar').hide();
}

open_test_edit = function(chart_filter_id, chart_test_id) {
    // Get the chart test data and open the dialog window
    url = "/dashboard/image-charts/+get-chart-test";

    $.ajax({
        url: url,
        data: {
            chart_filter_id: chart_filter_id,
            chart_test_id: chart_test_id},
        beforeSend: function () {
            $('#loading_dialog').dialog('open');
        },
        success: function (data) {
            $('#loading_dialog').dialog('close');
            set_chart_test_data(data);
        },
        error: function(data, status, error) {
            $('#loading_dialog').dialog('close');
            alert('Data could not be loaded, please try again.');
        }
    });
}

set_chart_test_data = function(data) {
    data = data[0];
    $("#dialog_test_name").html(data.test_name);
    $("#chart_test_id").val(data.id);
    $("#alias").val(data.name);
    $("#attributes").empty();
    $(data.all_attributes).each(function(iter, value) {
        $("#attributes").append($("<option>", {value: value, html: value}));
    });
    $("#attributes").val(data.attributes);
    $("#test_edit_dialog").dialog('open');
}
