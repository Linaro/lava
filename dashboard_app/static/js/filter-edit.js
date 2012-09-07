var row_number;
$(function () {
function updateTestCasesFromTest() {
    var test_id=$("#id_test option:selected").html();
    var select = $("#id_test_case");
    select.empty();
    select.append(Option("<any>", ""));
    if (test_id != '&lt;any&gt;') {
        $.ajax(
            {
                url: test_case_url + test_id,
                dataType: 'json',
                success: function (data) {
                    $(data).each(
                        function (index, val) {
                            select.append(Option(val.test_case_id, val.id));
                        });
                    select.removeAttr("disabled");
                }
            });
    } else {
        select.attr('disabled', 'disabled');
    }
};
$("#id_test").change(updateTestCasesFromTest);
var keyAutocompleteConfig = {
        source: attr_name_completion_url
    };
var valueAutocompleteConfig = {
        source: function (request, response) {
            var attrName = this.element.closest('tr').find('input.key').val();
            $.getJSON(
                attr_value_completion_url,
                {
                    'name': attrName,
                    'term': request.term
                },
                function (data) {
                    response(data);
                }
            );
        }
    };
$("#attributes-table tbody tr").formset(
    {
       prefix: "attributes"
    });
});