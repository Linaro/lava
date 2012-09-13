$(function () {
function updateTestCasesFromTest() {
    var test_id=$(this).find("option:selected").html();
    var selects = $(this).closest('tr').find('.test-case-formset select');
    selects.each(
        function () {
            $(this).empty();
        });
    if (test_id != '&lt;any&gt;') {
        $.ajax(
            {
                url: test_case_url + test_id,
                dataType: 'json',
                success: function (data) {
                    selects.each(
                        function () {
                            var select = $(this);
                            $(data).each(
                                function (index, val) {
                                    var test_case_id = val.test_case_id;
                                    if (test_case_id.length > 50) {
                                        test_case_id = test_case_id.substring(0, 50) + "...";
                                    }
                                    select.append(Option(test_case_id, val.id));
                                });
                            select.removeAttr("disabled");
                        });
                }
            });
    } else {
        selects.each(
            function () {
                $(this).attr('disabled', 'disabled');
            });
    }
};

$("#id_tests_empty_form .test-case-formset-empty select").attr('disabled', 'disabled');
$(".test-cell select").change(updateTestCasesFromTest);

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

var testSetSettings = {
    formTemplate: '#id_tests_empty_form',
    prefix: "tests",
    addText: "Add a test",
    added: formsetTestCase
};

function formsetTestCase(test_row, existing) {
    var addText;
    if (test_row.find(".test-case-formset select").size() < 2) {
        addText = 'Specify test cases';
    } else {
        addText = 'Add another test case';
    }

    var index = test_row.index();

    test_row.find(".test-case-formset > tbody > tr").formset(
        {
            formTemplate: test_row.find(".test-case-formset-empty"),
            formCssClass: "nested-dynamic-" + index,
            addText: addText,
            prefix: "tests-" + index,
            added: function (row2) {
                test_row.find('.add-row').text('Add another test case');
            },
            removed: function (row2) {
                if (test_row.find(".test-case-formset select").size() < 2) {
                    test_row.find('.add-row').text("Specify test cases");
                }
            }
        }
    );
}

$("#tests-table > tbody > tr").formset(testSetSettings);

$("#tests-table > tbody > tr").each(
    function () {
        formsetTestCase($(this));
    }
);

});