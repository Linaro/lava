function updateTestCasesFromTest() {
  var test_id=$("#id_test option:selected").html();
  if (test_id != '&lt;any&gt;') {
    $.ajax({
      url: test_case_url + test_id,
      dataType: 'json',
      success: function (data) {
        var select = $("#id_test_case");
        select.empty();
        select.append(Option("<any>", ""));
        $(data).each(function (index, val) {
          select.append(Option(val.test_case_id, val.id));
        });
        select.removeAttr("disabled");
      }
    });
  } else {
    $("#id_test_case").attr('disabled', 'disabled');
  }
};
var row_number;
$(function () { row_number = $("#attribute-table tbody tr").size(); 
$("#add-attribute").click(function (e) {
  e.preventDefault();
  var body = $("#attribute-table tbody");
  var row = $("#template-row").clone(true, true);
  row.show();
  row.find('.key').attr('id', 'id_attribute_key_' + row_number);
  row.find('.value').attr('id', 'id_attribute_value_' + row_number);
  row.find('.key').attr('name', 'attribute_key_' + row_number);
  row.find('.value').attr('name', 'attribute_value_' + row_number);
  row_number += 1;
  body.append(row);
});
$("#id_test").change(updateTestCasesFromTest);
$("a.delete-row").click(function (e) {
  e.preventDefault();
  $(this).closest('tr').remove();
});
});