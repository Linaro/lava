open_condition_modal = function(query_name, condition_id, table_id,
                                field, operator, value) {

    $("#condition_errors").html("");
    if (typeof(condition_id) === 'undefined') { // Add condition.
        // TODO: once table is back on the form, uncomment this.
        //$("#id_table").val("");
        $("#id_field").val("");
        $("#id_operator").val("");
        $("#id_value").val("");
        $("#condition_id").val("");
        $("#condition_form").attr("action", "+add-condition");
    } else { // Edit condition.
        $("#id_table").val(table_id);
        $("#id_field").val(field);
        $("#id_operator").val(operator);
        $("#id_value").val(value);
        $("#condition_id").val(condition_id);
        $("#condition_form").attr("action", condition_id +
                                  "/+edit-condition");
    }
    $("#condition_modal").modal("show");
}

$(document).ready(function () {

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
                        '<td>' + data[1].fields.name + '</td>' +
                        '<td>' + condition.field + '</td>' +
                        '<td>' + condition.operator + '</td>' +
                        '<td>' + condition.value + '</td>' +
                        '<td><a class="glyphicon glyphicon-edit" ' +
                        'aria-hidden="true" href="javascript: void(0);" ' +
                        'onclick="open_condition_modal(\'' +
                        query_name + '\',\'' + data[0].pk + '\',\'' +
                        condition.table + '\',\'' + condition.field + '\',\'' +
                        condition.operator + '\',\'' +
                        condition.value + '\');"></a></td>' +
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
});
