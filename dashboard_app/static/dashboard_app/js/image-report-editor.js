select_filter = function() {
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
            add_filter_container(data, name);
        },
        error: function(data, status, error) {
            $('#loading_dialog').dialog('close');
            alert('Filter could not be loaded, please try again.');
        }
    });
}

add_filter_container = function(data, title) {

    content = '<hr><div class="filter-title">' + title + '</div>';

    if ($('#id_chart_type').val() == "pass/fail") {
        test_label = "Tests";
    } else {
        test_label = "Test Cases";
    }

    content += '<div class="selector"><div class="selector-available"><h2>' +
        'Select ' + test_label + '</h2>';

    content += '<select id="available_tests" multiple class="filtered">';
    for (i in data) {
        if ($('#id_chart_type').val() == "pass/fail") {
            content += '<option value="' + data[i].pk + '">' +
                data[i].fields.test_id + '</option>';
        } else {
            content += '<option value="' + data[i].pk + '">' +
                data[i].fields.test_case_id + '</option>';
        }
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

    update_events();
}

update_events = function() {
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
}

move_options = function(from_element, to_element) {
    var options = $("#" + from_element + " option:selected");
    $("#" + to_element).append(options.clone());
    $(options).remove();

    update_aliases();
    toggle_alias();
}

add_selected_options = function() {
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
    $('#chosen_tests option').each(function() {
        if ($('#alias_' + $(this).val()).length == 0) {
            $('<input type="hidden" class="alias" name="aliases" id="alias_' + $(this).val() +
              '" />').appendTo($('#filters_div'));
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
    if ($('#chosen_tests option:selected').length == 1) {
        $('#alias_container').show();
        test_id = $('#chosen_tests option:selected').val();
        $('#alias').val($('#alias_' + test_id).val());
    } else {
        $('#alias_container').hide();
    }
}

copy_alias = function(e) {
    if ($('#chosen_tests option:selected').length == 1) {
        test_id = $('#chosen_tests option:selected').val();
        $('#alias_' + test_id).val(e.value);
    }
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
