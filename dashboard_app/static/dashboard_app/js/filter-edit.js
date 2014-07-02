window.jQuery(document).ready(function ($) {

    function updateTestCasesFromTest() {
        var test_id=$(this).find("option:selected").html();
        var selects = $(this).closest('tr').find('.test-case-formset select');
        selects.each(
            function () {
                $(this).empty();
            });
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
                                    select.append(new Option(test_case_id, val.id));
                                });
                            select.removeAttr("disabled");
                        });
                }
            });
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
            formCssClass: "attributes-dynamic-form",
            addText: "Add a required attribute",
            added: function(row) {
                row.find(".name input").unbind();
                row.find(".name input").autocomplete(nameAutocompleteConfig);
                row.find(".value input").unbind();
                row.find(".value input").autocomplete(valueAutocompleteConfig);
            }
        });

    $("#attributes-table tfoot").hide();

    var formsetCallCount = 0;

    function formsetTestCase(test_row) {
        var addText;
        if (test_row.find(".test-case-formset select").size() < 2) {
            addText = 'Specify test cases';
        } else {
            addText = 'Add another test case';
            test_row.find('> td:last').hide();
        }

        var index = test_row.parent().children('.test-dynamic-form').index(test_row);

        var fs = test_row.find(".test-case-formset > tbody > tr").formset(
            {
                formTemplate: test_row.find(".test-case-formset-empty"),
                formCssClass: "test-cases-dynamic-form-" + formsetCallCount,
                addText: addText,
                deleteText: "Remove test case",
                prefix: "tests-" + index,
                added: function (row2) {
                    test_row.find('.add-row').text('Add another test case');
                    test_row.find('> td:last').hide();
                },
                removed: function (row2) {
                    if (test_row.find(".test-case-formset select").size() < 2) {
                        test_row.find('.add-row').text("Specify test cases");
                        test_row.find('> td:last').show();
                    }
                }
            }
        );

        test_row.data('formset', fs);

        formsetCallCount += 1;
    }

    $("#tests-table > tbody > tr").formset(
        {
            formTemplate: '#id_tests_empty_form',
            prefix: "tests",
            formCssClass: "test-dynamic-form",
            addText: "Add a test",
            deleteText: "Remove test",
            added: formsetTestCase,
            removed: function () {
                $("#tests-table > tbody > tr.test-dynamic-form").each(
                    function () {
                        var index = $(this).parent().children('.test-dynamic-form').index($(this));
                        $(this).data('formset').data('options').prefix = 'tests-' + index;
                    });
            }
        }
    );


    $("#tests-table > tbody > tr").each(
        function () {
            formsetTestCase($(this));
        }
    );

    $("#tests-table tfoot").hide();

});
