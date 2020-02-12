open_condition_modal = function(query_name, condition_id, table_id,
                                field, operator, value) {

    $("#condition_errors").html("");

    // Initiate typeahead for "field" and "value"
    $("#id_field").attr("type", "search");
    $("#id_field").attr("placeholder", "Search");
    $("#id_field").attr("autocomplete", "off");
    $("#id_value").attr("type", "search");
    $("#id_value").attr("placeholder", "Search");
    $("#id_value").attr("autocomplete", "off");

    if (!$("#id_field").parent().attr("class")) {
        $("#id_field").wrap("<div class='typeahead__container'></div>").wrap("<div class='typeahead__field'></div>").wrap("<div class='typeahead__query'></div>");
    }
    if (!$("#id_value").parent().attr("class")) {
        $("#id_value").wrap("<div class='typeahead__container'></div>").wrap("<div class='typeahead__field'></div>").wrap("<div class='typeahead__query'></div>");
    }
    // End typeahead init.

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

        $("#id_tooltip_available_fields").remove();
	// Fire up the callbacks.
	table_changed();
	field_changed();
	$("#id_operator").val(operator);
    }

    $("#condition_modal").modal("show");
}

table_changed = function() {
    // Table field change callback.
    $("#id_field").typeahead({
        source: {
            data: Object.keys(condition_choices[$("#id_table").val()]["fields"])
        },
        order: "asc",
        minLength: 1,
        callback: {
            onClickAfter: "field_changed",
        }
    });

    $("#id_tooltip_available_fields").remove();
    if ($("#id_table option:selected").text() != "metadata") {
        $("[for='id_field']").next().after('<span id="id_tooltip_available_fields" class="btn btn-info btn-xs" data-toggle="tooltip" data-placement="right" title="test">?</span>').after("&nbsp;");
        $("#id_tooltip_available_fields").attr("title", "Available fields: " + Object.keys(condition_choices[$("#id_table").val()]["fields"]).join(", "));
    }
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
		$("#id_value").typeahead({
		    source: {
                        data: condition_field["choices"],
                    },
                    minLength: 1,
                    order: "asc",
		});
	    } else {
                $("#id_value").typeahead({source: {data: []}});
            }

	} else {
	    // Do nothing, validation will pick this up.
	}
    }
}


add_refresh_click_event = function() {
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
                    $("#query_results").removeClass('disabled');
                    $("#query_results").attr('title', 'View query results');
                    $("#query_results").attr('href', query_url);
		} else {
		    bootbox.alert("Update failed: " + data[2]);
		}
            },
	    error: function(data, status, error) {
                $('#refresh_loading_dialog').hide();
                bootbox.alert('Operation failed, please try again or contact system administrator.');
            }
        });
    });
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
                        if (is_live == "False") {
                            // Enable 'Run query' button.
                            $("#query_refresh").removeClass('disabled');
                            $("#query_refresh").attr('title', '');
                            add_refresh_click_event();
                        }
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
        $("#refresh_loading_dialog").append('<img src="/static/lava_results_app/images/ajax-progress.gif" alt="Loading..." />');
	if (is_updating == "False") {
            $('#refresh_loading_dialog').hide();
	}
    }
    init_loading_dialog();

    if (query_conditions != '') {
        add_refresh_click_event();
    }

    $("#id_table option:first").remove();
    $("#id_table").change(function () {
	$("#id_field").val("");
	table_changed();
    });
});
