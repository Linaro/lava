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

var nameAutocompleteConfig = {
        source: attr_name_completion_url
    };

var valueAutocompleteConfig = {
        source: function (request, response) {
            var attrName = this.element.closest('tr').find('.name input').val();
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

$("tbody .name input").autocomplete(nameAutocompleteConfig);
$("tbody .value input").autocomplete(valueAutocompleteConfig);

$("#attributes-table tbody tr").formset(
    {
        formTemplate: '#id_attributes_empty_form',
        prefix: "attributes",
        addText: "Add a required attribute",
        added: function(row) {
            row.find(".name input").unbind();
            row.find(".name input").autocomplete(nameAutocompleteConfig);
            row.find(".value input").unbind();
            row.find(".value input").autocomplete(valueAutocompleteConfig);
        }
    });

$("#tests-table > tbody > tr").formset(
    {
        formTemplate: '#id_tests_empty_form',
        prefix: "tests",
        addText: "Add a test",
        added: function(row) {
            console.log(row);
            console.log(row.find(".test-case-formset"));
            row.find(".test-case-formset > tbody > tr").formset(
                {
                    formTemplate: "#id_test_case_empty_form",
                    formCssClass: "nested-dynamic"
                    
                });
        }
    });

});