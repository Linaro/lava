function _resize() {
    // I couldn't figure out how to do this in CSS: resize the table
    // so that it takes as much space as it can without expanding the
    // page horizontally.
    var space = parseInt($("#lava-breadcrumbs").outerWidth() - $("#outer-table").outerWidth());
    console.log("in", parseInt($("#outer-table").outerWidth()));
    space -= $("#lava-content").outerWidth() - $("#lava-content").width();
    var table = $("#results-table"), scroller=$("#scroller");
    var atRight = scroller.width() + scroller.scrollLeft() >= table.attr('scrollWidth');
    scroller.width(scroller.width() + space);
    console.log("out", parseInt($("#outer-table").outerWidth()));
    if (atRight) scroller.scrollLeft(table.attr('scrollWidth'));
}
$(window).ready(
    function () {
        // Hook up the event and run resize ASAP (looks jumpy in FF if you
        // don't run it here).
        $(window).resize(_resize);
        $("#scroller").scrollLeft(100000);
        _resize();

        function _submit() {
            $(this).submit();
        }
        var add_bug_dialog = $('#add-bug-dialog').dialog(
            {
                autoOpen: false,
                buttons: {'Cancel': function () {$(this).dialog('close');}, 'OK': _submit },
                modal: true,
                title: "Link bug to XXX"
            });
        var go_to_bug_dialog = $("#go-to-bug-dialog").dialog(
            {
                autoOpen: false,
                buttons: {'Cancel': function () {$(this).dialog('close');}, 'Remove link': _submit},
                modal: true,
                title: "Link bug to XXX"
            });

        function get_testrun_and_buildnumber (element) {
            var cell = element.closest('td');
            var row = cell.closest('tr');
            var testrun = $($("#test-run-names > tbody > tr")[row.index()]).text();
            var header_cells = element.closest('table').find('thead > tr > th');
            var buildnumber = $(header_cells[cell.index()]).text();
            return {testrun: $.trim(testrun), buildnumber: $.trim(buildnumber)};
        }

        $('a.add-bug-link').click(
            function (e) {
                e.preventDefault();
                var names = get_testrun_and_buildnumber($(this));
                var title = "Link a bug to the '" + names.testrun +
                    "' run of build " + names.buildnumber;
                add_bug_dialog.find('input[name=uuid]').val($(this).closest('td').data('uuid'));
                add_bug_dialog.dialog('option', 'title', title);
                add_bug_dialog.dialog('open');
            });

        $("a.bug-link").click(
            function (e) {
                e.preventDefault();
                var names = get_testrun_and_buildnumber($(this));
                var title = "Bug linked to the '" + names.testrun +
                    "' run of build " + names.buildnumber;
                go_to_bug_dialog.find('input[name=uuid]').val($(this).closest('td').data('uuid'));
                go_to_bug_dialog.find('input[name=bug]').val($(this).data('bug-id'));
                go_to_bug_dialog.find('a').attr('href', $(this).attr('href'));
                go_to_bug_dialog.find('a').text('View bug ' + $(this).data('bug-id'));
                go_to_bug_dialog.dialog('option', 'title', title);
                go_to_bug_dialog.dialog('open');
            });
    });
// Because what resize does depends on the final sizes of elements,
// run it again after everything is loaded (things end up wrong in
// chromium if you don't do this).
$(window).load(_resize);
