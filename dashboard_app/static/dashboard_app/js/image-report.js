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

function update_filters(column_data, test_run_names) {
    for (iter in column_data) {
	build_number = column_data[iter]["number"].split('.')[0];
	$("#build_number_start").append($('<option>', {
	    value: build_number,
	    text: build_number
	}));
	$("#build_number_end").append($('<option>', {
	    value: build_number,
	    text: build_number
	}));
    }
    $("#build_number_end option:last").attr("selected", true);

    for (iter in test_run_names) {
	selected = false;
	if (column_data[column_data.length-1]["test_runs"][test_run_names[iter]]) {
	    selected = true;
	}
	$("#test_select").append($('<option>', {
	    value: test_run_names[iter],
	    text: test_run_names[iter],
	    selected: selected
	}));
    }
}

function update_table(column_data, table_data, test_run_names) {

    if ($("#test_select").val() == null) {
	alert("Please select at least one test.");
	return false;
    }

    if ($("#build_number_start").val() > $("#build_number_end").val()) {
	alert("End build number must be greater then the start build number.");
	return false;
    }

    // Create row headlines.
    test_name_rows = "<tr><td>Date</td></tr>";
    for (iter in test_run_names) {
	if ($("#test_select").val().indexOf(test_run_names[iter]) >= 0) {
	    test_name = test_run_names[iter];
	    if (test_name.length > 20) {
		test_name = test_name.substring(0,20) + "...";
	    }
	    test_name_rows += "<tr><td>" + test_name + "</td></tr>";
	}
    }
    $("#test-run-names tbody").html(test_name_rows);

    // Create column headlines.
    result_table_head = "<tr>";
    for (iter in column_data) {
	build_number = column_data[iter]["number"].split('.')[0];

	if (build_number <= $("#build_number_end").val() && build_number >= $("#build_number_start").val()) {
	    link = '<a href="' + column_data[iter]["link"] + '">' + build_number.split(' ')[0] + '</a>';
	    result_table_head += "<th>" + link + "</th>";
	}
    }
    result_table_head += "</tr>";
    $("#results-table thead").html(result_table_head);

    // Create table body
    result_table_body = "<tr>";
    for (iter in column_data) {
	build_number = column_data[iter]["number"].split('.')[0];
	build_date = column_data[iter]["date"].split('.')[0];

	if (build_number <= $("#build_number_end").val() && build_number >= $("#build_number_start").val()) {
	    result_table_body += "<td>" + build_date.split(' ')[0] + "</td>";
	}

    }
    result_table_body += "</tr>";

    for (test in table_data) {
	if ($("#test_select").val().indexOf(test) >= 0) {
	    result_table_body += "<tr>";
	    row = table_data[test];

	    for (iter in row) {
		build_number = column_data[iter]["number"].split('.')[0];
		if (build_number <= $("#build_number_end").val() && build_number >= $("#build_number_start").val()) {
		    result_table_body += '<td class="' + row[iter]["cls"] + '" data-uuid="' + row[iter]["uuid"] + '">';
		    if (row[iter]["uuid"]) {
			result_table_body += '<a href="' + row[iter]["link"] + '">' + row[iter]["passes"] + '/' + row[iter]["total"] + '</a>';
			result_table_body += '<span class="bug-links">';
			for (bug_id in row[iter]["bug_ids"]) {
			    bug = row[iter]["bug_ids"];
			    result_table_body += '<a class="bug-link" href="https://bugs.launchpad.net/bugs/' + bug[bug_id] + '" data-bug-id="' + bug[bug_id] + '">[' + bug[bug_id] + ']</a>';
			}
			result_table_body += '<a href="#" class="add-bug-link">[+]</a>';
			result_table_body += '</span>';

		    } else {
			result_table_body += "&mdash;";
		    }
		    result_table_body += "</td>";
		}
	    }
	    result_table_body += "</tr>";
	}
    }

    $("#results-table tbody").html(result_table_body);
    $("#scroller").scrollLeft($("#scroller")[0].scrollWidth);

    update_plot(column_data, table_data, test_run_names);
}

function update_plot(column_data, table_data, test_run_names) {

    // Get the plot data.

    data = [];
    for (test in table_data) {

	if ($("#test_select").val().indexOf(test) >= 0) {
	    row_data = [];

	    row = table_data[test];
	    for (iter in row) {
		build_number = column_data[iter]["number"].split('.')[0];
		if (build_number <= $("#build_number_end").val() && build_number >= $("#build_number_start").val()) {
		    if (row[iter]["cls"]) {
			if ($('input:radio[name=graph_type]:checked').val() == "number") {
			    row_data.push([iter, row[iter]["passes"]]); 
			} else {
			    row_data.push([iter, 100*row[iter]["passes"]/row[iter]["total"]]);
			}
		    }
		}
	    }
	    data.push({label: test, data: row_data});
	}
    }


    // Get all build numbers to be used as tick labels.
    build_numbers = [];
    for (test in table_data) {
	row = table_data[test];
	for (iter in row) {
	    build_number = column_data[iter]["number"].split('.')[0];
	    if (build_number <= $("#build_number_end").val() && build_number >= $("#build_number_start").val()) {
		build_numbers.push(build_number.split(' ')[0]);
	    }
	}
	// Each test has the same number of build numbers.
	break;
    }

    var options = {
	series: {
	    lines: { show: true },
	    points: { show: false }
	},
	legend: {
	    show: true,
	    position: "ne",
	    margin: 3,
	    container: "#legend-container",
	},
	xaxis: {
	    tickFormatter: function (val, axis) {
		return build_numbers[val];
	    },
	},
	yaxis: {
	    tickDecimals: 0,
	},
    };

    if ($('input:radio[name=graph_type]:checked').val() == "percentage") {
	options["yaxis"]["max"] = 100;
    }


    $.plot($("#outer-container #inner-container"), data, options); 
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
$(window).load(function() {update_filters(columns, test_names);});
$(window).load(function() {update_table(columns, chart_data, test_names);});
