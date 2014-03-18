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

function toggle_graph () {
    $("#outer-container").toggle();
    $(".tickLabels").toggle();
    update_plot(columns, chart_data, test_names);
    store_filters();
}

function update_filters(column_data, test_run_names) {
    for (iter in column_data) {
	build_number = column_data[iter]["number"].split('.')[0];
	build_date = column_data[iter]["date"];
	$("#build_number_start").append($('<option>', {
	    value: build_date,
	    text: build_number
	}));
	$("#build_number_end").append($('<option>', {
	    value: build_date,
	    text: build_number
	}));
    }
    start_number_options = $("#build_number_start option").size();
    // Show last 15 options.
    if (start_number_options > 15) {
        start_number_options -= 15;
        $("#build_number_start option:eq(" + start_number_options + ")").attr("selected", true);
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

    // Use jStorage to load the filter values from browser.
    load_filters();
}

function update_table(column_data, table_data, test_run_names) {

    if ($("#test_select").val() == null) {
	alert("Please select at least one test.");
	return false;
    }

    build_number_start = $("#build_number_start").val();
    if (isNumeric(build_number_start)) {
	build_number_start = parseInt(build_number_start);
    }
    build_number_end = $("#build_number_end").val();
    if (isNumeric(build_number_end)) {
	build_number_end = parseInt(build_number_end);
    }

    if (build_number_start > build_number_end) {
	alert("End build number must be greater then the start build number.");
	return false;
    }

    if ($("#target_goal").val() && !isNumeric($("#target_goal").val())) {
	alert("Target goal must be a numeric value.");
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
	    test_name_rows += "<tr><td tooltip='" + test_run_names[iter] + "'>" + test_name + "</td></tr>";
	}
    }
    $("#test-run-names tbody").html(test_name_rows);

    // Create column headlines.
    result_table_head = "<tr>";
    for (iter in column_data) {
	if (test_build_number(column_data, iter)) {

	    build_number = column_data[iter]["number"].split('.')[0];
	    if (!isNumeric(build_number)) {
		build_number = format_date(build_number.split(' ')[0]);
	    }
	    link = '<a href="' + column_data[iter]["link"] + '">' + build_number + '</a>';
	    result_table_head += "<th>" + link + "</th>";
	}
    }
    result_table_head += "</tr>";
    $("#results-table thead").html(result_table_head);

    // Create table body
    result_table_body = "<tr>";
    for (iter in column_data) {
	build_date = column_data[iter]["date"].split('.')[0];

	if (test_build_number(column_data, iter)) {
	    result_table_body += "<td>" + format_date(build_date.split(' ')[0]) + "</td>";
	}

    }
    result_table_body += "</tr>";

    for (cnt in test_run_names) {
        test = test_run_names[cnt];
        if ($("#test_select").val().indexOf(test) >= 0) {
            result_table_body += "<tr>";
            row = table_data[test];

            for (iter in row) {
                if (test_build_number(column_data, iter)) {
                    result_table_body += '<td class="' + row[iter]["cls"] + '" data-uuid="' + row[iter]["uuid"] + '">';
                    if (row[iter]["uuid"]) {
                        result_table_body += '<a href="' + row[iter]["link"] + '">' + row[iter]["passes"] + '/' + row[iter]["total"] + '</a>';
                        result_table_body += '<span class="bug-link-container"><a href="#" class="add-bug-link">[' + row[iter]["bug_links"].length + ']</a></span>';
                        result_table_body += '<span class="bug-links" style="display: none">';
                        for (bug_link in row[iter]["bug_links"]) {
                            bug = row[iter]["bug_links"];
                            result_table_body += '<li class="bug-link">' + bug[bug_link] + '</li>';
                        }
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

    // Use jStorage to save filter values to the browser.
    store_filters();
    update_plot(column_data, table_data, test_run_names);
    update_tooltips();
    update_filter_link();
    add_bug_links();
    _fixRowHeights();
}

function update_filter_link() {
    filter_link = window.location.href.split('?')[0] + '?';
    filter_link += "build_number_start=" + $("#build_number_start").val();
    filter_link += "&build_number_end=" + $("#build_number_end").val();
    filter_link += "&test_select=" + $("#test_select").val();
    filter_link += "&target_goal=" + $("#target_goal").val().trim();
    filter_link += "&graph_type=" + $('input:radio[name=graph_type]:checked').val();

    $("#filter_link").attr("href", filter_link);
}

function update_tooltips() {
    // Update tooltips on the remaining td's for the test names.
    $("td", "#test-run-names").each(function () {
	if ($(this).attr('tooltip')) {
	    $(this).tooltip({
		bodyHandler: function() {
		    return $(this).attr('tooltip');
		}
	    });
	}
    });
}

function store_filters() {
    // Use jStorage to save filter values to the browser.

    prefix = window.location.pathname.split('/').pop();

    $.jStorage.set(prefix + "_target_goal", $("#target_goal").val().trim());
    $.jStorage.set(prefix + "_build_number_start", $("#build_number_start").val());
    $.jStorage.set(prefix + "_test_select", $("#test_select").val());
    $.jStorage.set(prefix + "_toggle_graph", $("#toggle_graph").attr("checked"));
    $.jStorage.set(prefix + "_graph_type", $('input:radio[name=graph_type]:checked').val());
}

function load_filters() {
    // Use jStorage to load the filter values from browser.

    // If get parameters are present they are used because of higher priority.
    if (location.search != "") {
	populate_filters_from_get();
	return;
    }

    prefix = window.location.pathname.split('/').pop();

    if ($.jStorage.get(prefix + "_target_goal")) {
	$("#target_goal").val($.jStorage.get(prefix + "_target_goal"));
    }
    if ($.jStorage.get(prefix + "_build_number_start")) {
	$("#build_number_start").val($.jStorage.get(prefix + "_build_number_start"));
    }
    if ($.jStorage.get(prefix + "_test_select")) {
	$("#test_select").val($.jStorage.get(prefix + "_test_select"));
    }
    if ($.jStorage.get(prefix + "_toggle_graph") != null) {
	$("#toggle_graph").attr("checked", $.jStorage.get(prefix + "_toggle_graph"));
    }
    if ($.jStorage.get(prefix + "_graph_type")) {
	if ($.jStorage.get(prefix + "_graph_type") == "number") {
	    $('input:radio[name=graph_type][value="number"]').attr("checked", true);
	} else if ($.jStorage.get(prefix + "_graph_type") == "percentage") {
	    $('input:radio[name=graph_type][value="percentage"]').attr("checked", true);
	} else { // measurements
	    $('input:radio[name=graph_type][value="measurements"]').attr("checked", true);
	}
    }
}

function populate_filters_from_get() {
    // Populate filter fields from get request parameters.
    var parameters = get_parameters_from_request();
    for (iter in parameters) {
	if (parameters[iter][0] == "build_number_start" && parameters[iter][1] != "") {
	    $("#build_number_start").val(unescape(parameters[iter][1]));
	}
	if (parameters[iter][0] == "build_number_end" && parameters[iter][1] != "") {
	    $("#build_number_end").val(unescape(parameters[iter][1]));
	}
	if (parameters[iter][0] == "test_select" && parameters[iter][1] != "") {
	    $("#test_select").val(parameters[iter][1].split(','));
	}
	if (parameters[iter][0] == "target_goal" && parameters[iter][1] != "") {
	    $("#target_goal").val(unescape(parameters[iter][1]));
	}
	if (parameters[iter][0] == "graph_type" && parameters[iter][1] != "") {
	    if (parameters[iter][1] == "number") {
		$('input:radio[name=graph_type][value="number"]').attr("checked", true);
	    } else if (parameters[iter][1] == "percentage") {
		$('input:radio[name=graph_type][value="percentage"]').attr("checked", true);
	    } else { // measurements
		$('input:radio[name=graph_type][value="measurements"]').attr("checked", true);
	    }
	}
    }
}

function get_parameters_from_request() {
    var params = location.search.replace('?', '').split('&').map(function(val) {	
	return val.split('=');
    });
    return params;
}

function update_plot(column_data, table_data, test_run_names) {

    // Get the plot data.

    data = [];
    for (test in table_data) {

	if ($("#test_select").val().indexOf(test) >= 0) {
	    row_data = [];

	    row = table_data[test];
	    for (iter in row) {

		if (test_build_number(column_data, iter)) {
		    if (row[iter]["cls"]) {
			if ($('input:radio[name=graph_type]:checked').val() == "number") {
			    row_data.push([iter, row[iter]["passes"]]); 
			} else if ($('input:radio[name=graph_type]:checked').val() == "percentage") {
			    if (isNaN(row[iter]["passes"]/row[iter]["total"])) {
				row_data.push([iter, 0]);
			    } else {
				row_data.push([iter, 100*row[iter]["passes"]/row[iter]["total"]]);
			    }
			} else { // measurements
			    if (row[iter]["measurements"] && row[iter]["measurements"].length != 0) {
				row_data.push([iter, row[iter]["measurements"][0]["measurement"]]);
			    }
			}
		    }
		}
	    }
	    data.push({label: test, data: row_data});
	}
    }

    // Add target goal dashed line to the plot.
    if ($("#target_goal").val()) {
	row_data = [];
	row = table_data[test_run_names[0]];
	for (iter in row) {
	    if (test_build_number(column_data, iter)) {
		row_data.push([iter, $("#target_goal").val()]);
	    }
	}
	data.push({data: row_data, dashes: {show: true}, lines: {show: false}, color: "#000000"});
    }

    // Get all build numbers to be used as tick labels.
    build_numbers = [];
    for (test in table_data) {
	row = table_data[test];
	for (iter in row) {
	    build_number = column_data[iter]["number"].split(' ')[0];
	    if (!isNumeric(build_number)) {
		build_number = format_date(build_number);
	    }
	    build_numbers.push(build_number);
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
	    labelFormatter: function(label, series) {
		if (label.length > 20) {
		    return label.substring(0,20) + "...";
		}
		return label;
	    },
	},
	xaxis: {
	    tickDecimals: 0,
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
	options["yaxis"]["min"] = 0;
    }

    $.plot($("#outer-container #inner-container"), data, options); 
}

function test_build_number(column_data, iter) {
    // Test if the build number/date is between specified number/date boundaries.

    var build_number = column_data[iter]["date"];

    if (build_number <= $("#build_number_end").val() && build_number >= $("#build_number_start").val()) {
	return true;
    }

    return false;
}

function isNumeric(n) {
    return !isNaN(parseFloat(n)) && isFinite(n);
}

function isValidUrl(url)
{
    return url.match(/^https?:\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>\#%"\,\{\}\\|\\\^\[\]`]+)?$/);
}

function format_date(date_string) {
    date = $.datepicker.parseDate("yy-mm-dd", date_string);
    date_string = $.datepicker.formatDate("M d, yy", date);
    return date_string;
}

function add_bug_links() {

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
                function () {
                    var bug_link = $(this).text();
                    if (bugs.indexOf(bug_link) < 0) bugs.push(bug_link);
                });
        }
        var already_linked = [];
        start.find(".bug-link").each(
            function () {
                var bug_link = $(this).text();
                if (bugs.indexOf(bug_link) >= 0) {
                    bugs.splice(bugs.indexOf(bug_link), 1);
                    already_linked.push(bug_link);
                }
            });
        return {bugs:bugs, already_linked:already_linked};
    }

    function get_linked_bugs (element) {
        var start = $(element).closest('td');
        var bugs = [];

        start.find(".bug-link").each(
            function () {
                var bug_link = $(this).text();
                bugs.push(bug_link);
            }
        )
        return bugs;
    }

    $('a.add-bug-link').click(
        function (e) {
            e.preventDefault();

            var previous = find_previous_bugs($(this));
            var prev_div = add_bug_dialog.find('div.prev');
            var linked_div = add_bug_dialog.find('div.linked');
            var names = get_testrun_and_buildnumber($(this));
            var uuid = $(this).closest('td').data('uuid');

            current_bug = get_linked_bugs($(this));
            add_bug_dialog.find('input[name=bug_link]').val('');

            if(current_bug.length) {
                var html = '<b>Bug(s) linked to ' + names.testrun + ':</b><table width="95%" border="0">';
                linked_div.show();
                for (bug in current_bug) {
                    html += '<tr>';
                    html += '<td><a id="linked-bug" href="#">' + current_bug[bug] + '</a></td>';
                    html += '<td width="16"><a id="unlink-bug" href="#" data-bug-link="' + current_bug[bug] + '"><img src="'+image_url+'icon-bug-delete.png" width="16" height="16" title="Unlink this bug"></a></td></tr>';
                }
                html += '</table><hr>';
                linked_div.html(html);
                $('a#linked-bug').click(
                    function (e) {
                        e.preventDefault();
                        window.open($(this).text());
                    }
                );
                $('a#unlink-bug').click(
                    function (e) {
                        var bug = $(this).data('bug-link');

                        e.preventDefault();
                        if(confirm("Unlink '" + bug + "'")) {
                            // unlink bug right now, so clear current_bug which is used for checking if the bug is duplicated when adding a bug
                            current_bug = [];
                            $('#add-bug-dialog').attr('action', del_bug_url);
                            add_bug_dialog.find('input[name=bug_link]').val(bug);
                            add_bug_dialog.find('input[name=uuid]').val(uuid);
                            add_bug_dialog.submit();
                        }
                    }
                );
            } else {
                linked_div.hide();
            }

            if (previous.bugs.length) {
                var html = '';
                prev_div.show();
                html = '<b>Use a bug previously linked to ' + names.testrun + ':</b><table width="95%">';
                for (var i = 0; i < previous.already_linked.length; i++) {
                    html += '<tr><td style="text-decoration: line-through">' + previous.already_linked[i] + '</td><td><img src="'+image_url+'icon-bug-link.png" width="16" height="16" title="This bug already linked"></td></tr>';
                }
                for (var i = 0; i < previous.bugs.length; i++) {
                    html += '<tr><td>' + previous.bugs[i] + '</td><td width="16"><a href="#" data-bug-link="' + previous.bugs[i] + '"><img src="'+image_url+'icon-bug-add.png" width="16" height="16" title="Link this bug"></a></td></tr>';
                }
				html += '</table><hr>';
                html += "<b>Or enter another bug link:</b>";
                prev_div.html(html);
                prev_div.find('a').click(
                    function (e) {
                        var bug = $(this).data('bug-link');

                        e.preventDefault();
                        if (confirm("Link '" + bug + "' to the '" + names.testrun + "' run of build" + names.buildnumber)) {
                            add_bug_dialog.find('input[name=bug_link]').val(bug);
                            add_bug_dialog.submit();
                        }
                    });
            } else {
                prev_div.hide();
            }

            var title = "Link a bug to the '" + names.testrun +
                "' run of build " + names.buildnumber;
            add_bug_dialog.find('input[name=uuid]').val(uuid);
            add_bug_dialog.dialog('option', 'title', title);
            add_bug_dialog.dialog('open');
        });
}

$(window).ready(
    function () {
	update_filters(columns, test_names);
	update_table(columns, chart_data, test_names);
        // Hook up the event and run resize ASAP (looks jumpy in FF if you
        // don't run it here).
        $(window).resize(_resize);
        _resize();
        _fixRowHeights();

	add_bug_links();
	if (!$("#toggle_graph").attr("checked")) {
	    $("#outer-container").toggle();
	}

    });
// Because what resize does depends on the final sizes of elements,
// run it again after everything is loaded (things end up wrong in
// chromium if you don't do this).
$(window).load(_resize);
$(window).load(_fixRowHeights);

