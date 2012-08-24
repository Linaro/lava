function _resize() {
    // I couldn't figure out how to do this in CSS: resize the table
    // so that it takes as much space as it can without expanding the
    // page horizontally.
    var space = parseInt($("#lava-breadcrumbs").outerWidth() - $("#outer-table").outerWidth());
    space -= $("#lava-content").outerWidth() - $("#lava-content").width();
    var table = $("#results-table"), scroller=$("#scroller");
    var atRight = scroller.width() + scroller.scrollLeft() >= table.attr('scrollWidth');
    scroller.width(scroller.width() + space);
    if (atRight) scroller.scrollLeft(table.attr('scrollWidth'));
}
function _fixRowHeights () {
    var index = 0;
    var nameRows = $("#test-run-names > tbody > tr");
    var resultRows = $("#results-table > tbody > tr");
    for (; index < nameRows.length; index++) {
        var nameRow = $(nameRows[index]);
        var resultRow = $(resultRows[index]);
        var nameRowHeight = parseInt(nameRow.css('height'));
        var resultRowHeight = parseInt(resultRow.css('height'));
        nameRow.css('height', Math.max(nameRowHeight, resultRowHeight));
        resultRow.css('height', Math.max(nameRowHeight, resultRowHeight));
    }
}
$(window).ready(
    function () {
        // Hook up the event and run resize ASAP (looks jumpy in FF if you
        // don't run it here).
        $(window).resize(_resize);
        $("#scroller").scrollLeft(100000);
        _resize();
        _fixRowHeights();

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

        function find_previous_bugs (element) {
            var td = $(element).closest('td');
            var bugs = [];
            var start = td;
            while ((td = td.prev()) && td.size()) {
                td.find(".bug-link").each(
                    function (index, link) {
                        var bug_id = $(link).data('bug-id');
                        if (bugs.indexOf(bug_id) < 0) bugs.push(bug_id);
                    });
            }
            var already_linked = [];
            start.find(".bug-link").each(
                function (index, link) {
                    var bug_id = $(link).data('bug-id');
                    if (bugs.indexOf(bug_id) >= 0) {
                        bugs.splice(bugs.indexOf(bug_id), 1);
                        already_linked.push(bug_id);
                    }
                });
            return {bugs:bugs, already_linked:already_linked};
        }

        $('a.add-bug-link').click(
            function (e) {
                e.preventDefault();

                var previous = find_previous_bugs($(this));
                var prev_div = add_bug_dialog.find('div.prev');
                var names = get_testrun_and_buildnumber($(this));

                if (previous.bugs.length) {
                    var html = '';
                    prev_div.show();
                    html = '<p>Use a bug previously linked to ' + names.testrun + ':</p><ul>';
                    for (var i = 0; i < previous.already_linked.length; i++) {
                        html += '<li><span style="text-decoration: line-through">' + previous.already_linked[i] + '</span> (already linked)</li>';
                    }
                    for (var i = 0; i < previous.bugs.length; i++) {
                        html += '<li><a href="#" data-bug-id="' + previous.bugs[i] + '">' +
                            previous.bugs[i] + '</a></li>';
                    }
                    html += '</ul>';
                    html += "<p>Or enter another bug number:</p>";
                    prev_div.html(html);
                    prev_div.find('a').click(
                        function (e) {
                            e.preventDefault();
                            add_bug_dialog.find('input[name=bug]').val($(this).data('bug-id'));
                            add_bug_dialog.submit();
                        });
                } else {
                    prev_div.hide();
                }

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
$(window).load(_fixRowHeights);
