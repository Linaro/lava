open_condition_modal = function(query_name, condition_id, table_id,
                                field, operator, value) {

    $("#condition_errors").html("");
    if (typeof(condition_id) === 'undefined') { // Add condition.
        $("#id_table").val("");
        $("#id_field").val("");
        $("#id_operator").val("");
        $("#id_value").val("");
        $("#condition_id").val("");
        $("#condition_form").attr("action", "+add-condition");
    } else { // Edit condition.
        $("#id_table").val(table_id);
        $("#id_field").val(field);
        $("#id_value").val($("<textarea/>").html(value).val());
        $("#condition_id").val(condition_id);
        $("#condition_form").attr("action", condition_id +
                                  "/+edit-condition");

	// Fire up the callbacks.
	table_changed();
	field_changed();
	$("#id_operator").val(operator);
    }

    $("#condition_modal").modal("show");
}

table_changed = function() {
    // Table field change callback.

    $("#id_field").autocomplete({
        source: Object.keys(condition_choices[$("#id_table").val()]["fields"]),
        minLength: 0,
	autoFocus: true,
	appendTo: $("#id_table").parent()
    });
}

field_changed = function() {
    // Field 'field' change callback.

    // Set operator options based on the field type.
    $("#id_operator").empty();
    condition_fields = condition_choices[$("#id_table").val()]["fields"];
    if ($.isEmptyObject(condition_fields)) {
	$.each(initial_operators, function(value,key) {
	    $("#id_operator").append($("<option></option>")
				     .attr("value", value).text(key));
	});

    } else {
	if ($("#id_field").val() in condition_fields) {
	    condition_field = condition_fields[$("#id_field").val()];
	    $.each(condition_field["operators"], function(value,key) {
		$("#id_operator").append($("<option></option>")
					 .attr("value", value).text(key));
	    });
	    if (condition_field["type"] == "DateTimeField") {
		$("#id_value").parent().append(
		    "<span id='format'>&nbsp;Format: " +
			condition_choices['date_format'] + "</span>");
	    } else {
		$("#format").remove();
	    }

	    if (condition_field["choices"]) {
		$("#id_value").autocomplete({
		    source: condition_field["choices"],
		    minLength: 0,
		    autoFocus: true,
		    appendTo: $("#id_table").parent()
		});
	    }

	} else {
	    // Do nothing, validation will pick this up.
	}
    }
}

$(document).ready(function () {
    // Define callbacks and events.

    submit_modal_dialog = function(form_selector, dialog_selector,
                                   matchString){
        $.ajax({
            url: $(form_selector).attr('action'),
            type: 'POST',
            data:  $(form_selector).serialize(),
            success: function(data, textStatus, jqXHR){
                if(data[0] == 'fail'){
                    error_msg = '<ul>';
                    for (field in data[1]) {
                        error_msg += '<li>' + field +
                            ': ' + data[1][field] +
                            '</li>';
                    }
                    error_msg += '</ul>';

                    $("#condition_errors").html(error_msg);
                    return false;
                } else {
                    condition = data[0].fields;

                    condition_row_html =
                        '<td>' + data[1].fields.model + '</td>' +
                        '<td>' + condition.field + '</td>' +
                        '<td>' + condition.operator + '</td>' +
                        '<td>' + condition.value + '</td>' +
			'<td><a class="glyphicon glyphicon-edit" ' +
                        'aria-hidden="true" href="javascript: void(0);" ' +
                        'onclick="open_condition_modal(\'' +
                        query_name + '\',\'' + data[0].pk + '\',\'' +
                        condition.table + '\',\'' + condition.field + '\',\'' +
                        condition.operator + '\',\'' +
			$("<textarea/>").text(condition.value).html() +
			'\');"></a></td>' +
                        '<td><a class="glyphicon glyphicon-remove" ' +
                        'aria-hidden="true" href="/results/query/~' +
                        query_user + '/' + query_name + '/' +
                        data[0].pk + '/+remove-condition"></a></td>';

                    if ($("#condition_id").val() != "") {
                        $("#condition_row_" + $("#condition_id").val()).html(
                            condition_row_html);
                    } else {

                        $("#conditions_container").find("tbody").append(
                            '<tr id="condition_row_' + data[0].pk + '">' +
                                condition_row_html + '</tr>'
                        );
                    }
                    $(dialog_selector).modal('hide');
                }
            },
        });
    }

    $("#save_condition").click(function() {
        submit_modal_dialog('#condition_form', '#condition_modal',
                            'invalid_form')
    });

    init_loading_dialog = function() {
	// Setup the loading image dialog.
        $("#refresh_loading_dialog").append('<img src="/static/dashboard_app/images/ajax-progress.gif" alt="Loading..." />');
	if (is_updating == "False") {
            $('#refresh_loading_dialog').hide();
	}
    }
    init_loading_dialog();

    $("#query_refresh").click(function() {
        $.ajax({
            url: "+refresh",
            type: 'POST',
	    data: {csrfmiddlewaretoken: csrf_token},
	    beforeSend: function () {
                $('#refresh_loading_dialog').show();
            },
            success: function(data, textStatus, jqXHR){
		$('#refresh_loading_dialog').hide();
		if (data[0] == true) {
		    $('#last_updated').html(data[1]);
		} else {
		    alert("Update failed: " + data[2]);
		}
            },
	    error: function(data, status, error) {
                $('#refresh_loading_dialog').hide();
                alert('Operation failed, please try again or contact system administrator.');
            }
        });
    });

    $("#id_table option:first").remove();
    $("#id_table").change(function () {
	$("#id_field").val("");
	table_changed();
    });
    $("#id_field").on("autocompletechange", field_changed);

});
