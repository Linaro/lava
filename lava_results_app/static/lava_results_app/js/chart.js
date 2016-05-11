$(document).ready(function () {

    function Chart(chart_data) {
        this.chart_data = chart_data;
        this.charts = [];
    }

    Chart.prototype.start = function() {
        // Add charts.
        for (index in this.chart_data) {
            chart = new ChartQuery(this.chart_data[index]["basic"].id,
                                   this.chart_data[index]);
            chart.add_chart();
            this.charts.push(chart);
        }
    }

    Chart.prototype.redraw = function() {
        // Add charts.
        for (var i in this.charts) {
            this.charts[i].update_plot();
        }
    }

    function ChartQuery(chart_id, chart_data) {
        this.plot = null;
        this.chart_id = chart_id;
        this.chart_data = chart_data;
        this.legend_items = {};
    }

    ChartQuery.prototype.BUILD_NUMBER_ERROR =
        "End build number must be greater then the start build number.";

    ChartQuery.prototype.add_chart = function() {

        if (this.chart_data.data) {

            // Add chart container.
            $("#main_container").append(
                '<div id="chart_container_'+ this.chart_id + '"></div>');
            // Add headline container.
            $("#chart_container_" + this.chart_id).append(
                '<div class="headline-container" id="headline_container_' +
                    this.chart_id + '"></div>');
            // Add data table link.
            $("#chart_container_" + this.chart_id).append(
                '<div class="table-link-container"' +
                    'id="table_link_container_' + this.chart_id + '"></div>');
            // Add toggle options.
            $("#chart_container_" + this.chart_id).append(
                '<div class="toggle-options-container"' +
                    'id="toggle_options_container_' + this.chart_id +
                    '"></div>');
            // Add dates/build numbers container.
            $("#chart_container_" + this.chart_id).append(
                '<div class="dates-container" id="dates_container_' +
                    this.chart_id + '"></div>');
            // Add outer plot container.
            $("#chart_container_" + this.chart_id).append(
                '<div class="outer-chart" id="outer_container_' +
                    this.chart_id + '"></div>');
            // Add inner plot container.
            $("#outer_container_" + this.chart_id).append(
                '<div class="inner-chart" id="inner_container_' +
                    this.chart_id + '"></div>');
            // Add legend container.
            $("#outer_container_" + this.chart_id).append(
                '<div class="legend" id="legend_container_' +
                    this.chart_id + '"></div>');

            // Set chart height.
            $("#inner_container_" + this.chart_id).height(
                this.chart_data.basic.chart_height
            );
            // Set chart legend height.
            $("#legend_container_" + this.chart_id).height(
                this.chart_data.basic.chart_height
            );

            // Determine whether dates/attributes are numeric .
            this.is_keys_numeric();
            // Add headline and description.
            this.update_headline();
            // Add options.
            this.update_toggle_options();
            // Add dates/build numbers.
            this.update_dates();
            // Add data tables.
            this.update_data_tables();
            // Generate chart.
            this.update_plot();
            // Add source for saving charts as images and custom charts.
            this.update_urls();
            // Update events.
            this.update_events();
            // Update chart/table visibility.
            this.update_visibility();
        }
    }

    ChartQuery.prototype.is_keys_numeric = function() {

        keys = this.get_keys();
        // Check if all range items are numeric and set the value in chart_data.
        this.chart_data.basic.is_keys_numeric = is_array_numeric(keys);

        this.chart_data.is_keys_decimal = false;
        if (this.chart_data.basic.is_keys_numeric) {
            this.chart_data.is_keys_decimal = is_any_element_decimal(keys);
        }
    }

    ChartQuery.prototype.get_keys = function() {

        // Get all keys based on chart options.
        keys = [];
        for (iter in this.chart_data.data) {
            if (this.chart_data.basic.xaxis_attribute) {
                item = this.chart_data.data[iter]["attribute"];
            } else {
                item = this.chart_data.data[iter]["date"].split('.')[0];
            }
            if (item && keys.indexOf(item) == -1) {
                keys.push(item);
            }
        }

        return keys;
    }

    ChartQuery.prototype.setup_print_menu = function() {
        chart_id = this.chart_id;
        $("#print_menu_" + chart_id).menu();
        $("#print_menu_" + chart_id).hide();
        $("#print_menu_" + chart_id).mouseleave(function() {
            $("#print_menu_" + chart_id).hide();
        });
    }

    ChartQuery.prototype.setup_item_menu = function() {
        chart_id = this.chart_id;
        $("#item_menu_" + chart_id).menu();
        $("#item_menu_" + chart_id).hide();
        $("#item_menu_" + chart_id).mouseleave(function() {
            $("#item_menu_" + chart_id).hide();
        });
    }

    ChartQuery.prototype.update_events = function() {

	// Add item menu.
	$("#chart_container_" + this.chart_id).append(
            '<ul class="print-menu" id="item_menu_' + this.chart_id + '">' +
		'<li class="print-menu-item"><a target="_blank" href="#"' +
		' id="view_item_' + this.chart_id + '">View result</a></li>' +
		'<li class="print-menu-item"><a href="#"' + ' id="omit_item_' +
		this.chart_id + '" data-toggle="confirm" data-title="This ' +
                'will affect underlying query. Are you sure you want to omit' +
                ' this result?">' +
                'Omit result</a></li>' +
                '</ul>');
        this.setup_item_menu();

        // Bind plotclick event.
	chart_id = this.chart_id;
	chart_name = this.chart_data.basic.chart_name;
        $("#inner_container_" + this.chart_id).bind(
            "plotclick",
            function (event, pos, item) {
                if (item) {
                    // Make datapoint unique value
                    datapoint = item.datapoint.join("_");
		    toggle_item_menu(chart_id, pos.pageX, pos.pageY);
		    $("#view_item_" + chart_id).attr("href", window.location.protocol + "//" + window.location.host + item.series.meta[datapoint]["link"]);
		    $("#omit_item_" + chart_id).attr(
			"href",
			window.location.protocol + "//" +
			    window.location.host + "/results/chart/" +
			    chart_name + "/" +
			    chart_id + "/" +
			    item.series.meta[datapoint]["pk"] +
			    "/+omit-result");
                }
            });

        // Now setup the click event for omit link (needed for bootbox dialog).
        add_bootbox_data_toggle();

        $("#inner_container_" + this.chart_id).bind(
            "plothover",
            function (event, pos, item) {
                $("#tooltip").remove();
                if (item) {
                    // Make datapoint unique value
                    datapoint = item.datapoint.join("_");
                    tooltip = item.series.meta[datapoint]["tooltip"];
                    showTooltip(item.pageX, item.pageY, tooltip,
                                item.series.meta[datapoint]["pass"]);
                }
            });
    }

    ChartQuery.prototype.update_headline = function() {
	if (this.chart_data.basic.query_name) {
            query_link = this.chart_data.basic.query_link.replace(/\\/g, "");
            if (this.chart_data.basic.query_live) {
                last_updated = "Live query";
            } else {
                last_updated = "Last updated: " +
                    this.chart_data.basic.query_updated;
            }
            $("#headline_container_" + this.chart_id).append(
		'<span class="chart-headline">' +
                    '<a href="' + query_link + '" target="_blank">' +
		    this.chart_data.basic.query_name +
                    '</a></span> <span>' + last_updated +
                    '</span>');
            $("#headline_container_" + this.chart_id).append(
		'<div>' + this.chart_data.basic.query_description + '</div>');

	    if (this.chart_data.basic.has_omitted) {
                $("#headline_container_" + this.chart_id).append(
                    '<div class="alert alert-info">' +
                        '<button type="button" class="close" ' +
                        'data-dismiss="alert">&times;</button>' +
                        '<strong>This chart has some of the results omitted.' +
                        '</strong> ' +
                        'Check the underlying <strong><a href="' + query_link +
                        '" target="_blank">' + 'query</a></strong> ' +
                        'for the list of omitted results.' +
                        '</div>');
	    }
	}
    }

    ChartQuery.prototype.update_toggle_options = function() {

        // Add legend toggle checkbox.
        $("#toggle_options_container_" + this.chart_id).append(
            '<span class="toggle-legend"><label for="is_legend_visible_' +
                this.chart_id + '">Toggle legend</label></span>');
        $("#toggle_options_container_" + this.chart_id).append(
            '<span class="toggle-checkbox"><input type="checkbox" ' +
                'id="is_legend_visible_' + this.chart_id +
                '" checked="checked"/></span>');

        // Add delta reporting checkbox.
        $("#toggle_options_container_" + this.chart_id).append(
            '<span class="toggle-delta"><label for="is_delta_' +
                this.chart_id + '">Delta reporting</label></span>');
        $("#toggle_options_container_" + this.chart_id).append(
            '<span class="toggle-checkbox"><input type="checkbox" ' +
                'id="is_delta_' + this.chart_id +
                '" checked="checked"/></span>');

        $("#toggle_options_container_" + this.chart_id).append(
            '<span class="chart-save-img">' +
                '<a id="chart_menu_' + this.chart_id + '"' +
                ' onclick="toggle_print_menu(event, ' + this.chart_id + ')">' +
                '<img src="' + image_url + 'icon-print.png"></a>' +
                '</span>');

        image_html = '<li class="print-menu-item"><a target="_blank" href="#"' +
            ' id="chart_img_' + this.chart_id + '">View as image</a></li>';

        url_html = '<li class="print-menu-item"><a target="_blank" href="' +
            custom_chart_url + '?entity=' + this.chart_data.basic.entity +
            '&conditions='  + this.chart_data.basic.conditions +
            '&type='  + this.chart_data.basic.chart_type + '"' +
            ' id="chart_url_' + this.chart_id +
            '">This chart by URL</a></li>';

        if (this.chart_id == 0) {
            // We use 0 for chart_id for custom charts.
            print_menu_html = image_html;
        } else {
            print_menu_html = image_html + url_html;
        }

        $("#toggle_options_container_" + this.chart_id).append(
            '<ul class="print-menu" id="print_menu_' + this.chart_id + '">' +
                print_menu_html +
            '</ul>');


        this.setup_print_menu();
    }

    ChartQuery.prototype.update_dates = function() {

        // Add dates(build number) fields and toggle legend checkbox.
        $("#dates_container_" + this.chart_id).append(
            '<span style="margin-left: 30px;">Start:&nbsp;' +
                '&nbsp;</span>');
        $("#dates_container_" + this.chart_id).append(
            '<span><select id="start_date_' + this.chart_id +
                '"></select></span>');
        $("#dates_container_" + this.chart_id).append(
            '<span>&nbsp;&nbsp;&nbsp;&nbsp;End:&nbsp;&nbsp;' +
                '</span>');
        $("#dates_container_" + this.chart_id).append(
            '<span><select id="end_date_' + this.chart_id + '"></select>' +
                '</span>');
        $("#dates_container_" + this.chart_id).append(
            '<span style="float: right;"><input id="has_subscription_' +
                this.chart_id +
                '" type="hidden"/><a id="has_subscription_link_' +
                this.chart_id + '" href="javascript:void(0)"></a></span>');

        this.set_dates();
        this.apply_settings();
        this.add_settings_events();
    }


    ChartQuery.prototype.result_table_as_dialog = function() {

	$("#data_table_dialog_" + this.chart_id).attr("class", "modal fade");
	$("#table_dialog_" + this.chart_id).attr(
	    "class", "modal-dialog data-table-modal");
	$("#table_content_" + this.chart_id).attr("class", "modal-content");
	$("#table_content_" + this.chart_id).prepend(
	    '<div class="modal-header">Results Table<button type="button"' +
		'class="close" data-dismiss="modal"' +
		'aria-hidden="true">&times;</button></div>');
	$("#data_table_inner_" + this.chart_id).attr("class", "modal-body");
    }

    ChartQuery.prototype.update_visibility = function() {
        if (this.chart_data.basic.chart_visibility == 'table') {
            $("#outer_container_" + this.chart_id).hide();
            $("#table_link_container_" + this.chart_id).hide();
            $("#toggle_options_container_" + this.chart_id).hide();
            $("#dates_container_" + this.chart_id).hide();
        } else if (this.chart_data.basic.chart_visibility == 'both') {
            $("#table_link_container_" + this.chart_id).hide();
        }
    }

    ChartQuery.prototype.update_data_tables = function() {

        // Add dialog.
        $("#chart_container_" + this.chart_id).append(
            '<div id="data_table_dialog_' + this.chart_id +
		'" tabindex="-1">' +
		'<div id="table_dialog_' + this.chart_id + '">' +
		'<div id="table_content_' + this.chart_id + '">' +
		'<div id="data_table_inner_' + this.chart_id + '">' +
		'</div></div></div></div>');

        if (this.chart_data.basic.chart_visibility == 'chart') {
            this.result_table_as_dialog(this.chart_id);
        }

        // Add skeleton data to dialog.
        $("#data_table_inner_" + this.chart_id).append(
            '<table id="outer-table"><tr><td>' +
                '<table id="test-run-names_' + this.chart_id +
                '" class="inner-table-names"><thead>' +
                '<tr><th>Date</th></tr>' +
                '</thead>' +
                '<tbody></tbody></table></td>' +
                '<td><div class="scroller">' +
                '<table id="results-table_' + this.chart_id +
                '" class="inner-table"><thead>' +
                '</thead><tbody></tbody></table>' +
                '</div></td></tr></table>');

        // Add data.
        this.add_table_data();

        // Add link.
        $("#table_link_container_" + this.chart_id).append(
            '<a id="data_table_link_' +
                this.chart_id +
                '" href="javascript:void(0)">Results table</a>');

        $('#data_table_dialog_' + this.chart_id).css('overflow', 'hidden');

        $('.scroller').each(function() {
            $(this).scrollLeft($(this)[0].scrollWidth);
        });

        var chart = this;
        $("#data_table_link_" + this.chart_id).click(function(){
            $('#data_table_dialog_' + chart.chart_id).modal("show");
        });
    }

    ChartQuery.prototype.add_table_data = function() {

        // Create row headlines.
	has_xaxis_attribute = this.chart_data.basic.xaxis_attribute != "";
	if (has_xaxis_attribute) {
            table_rows = "<tr><td>" + this.chart_data.basic.xaxis_attribute +
		"</td></tr>";
	} else {
	    table_rows = "";
	}

        // Array with row names.
        rows = [];
        // Array with column strings
        columns = [];
        // Inner table data.
        table = {};

        // Create inner table with row names.
        for (iter in this.chart_data.data) {

            test_data = this.chart_data.data[iter];
            if ($.inArray(test_data.id, rows) == -1) {
                // Add unique rows and create row headlines HTML.

                rows.push(test_data.id);

                test_name = test_data.id.replace(/\\/g , "");
                table_rows += "<tr><td title='" + test_data.id.replace(/\\/g , "") +
                    "'>" + test_name + "</td></tr>";
            }
        }
        $("#test-run-names_" + this.chart_id + " tbody").html(table_rows);

        // Organize data in the 'table' multi array.
        for (iter in this.chart_data.data) {
            test_data = this.chart_data.data[iter];

            index = test_data.attribute.split(' ')[0];
            if (!(index in table)) {
                table[index] = {};
            }

            if (!(test_data.id in table[index])) {
                table[index][test_data.id] = [];
            }

            measurement = parseFloat(test_data["measurement"]);
            if (isNaN(measurement)) {
                measurement = test_data["measurement"];
            }

            table[index][test_data.id].push({
                "passes": test_data["passes"],
                "pass": test_data["pass"],
                "skip": test_data["skip"],
                "total": test_data["total"],
		"date": test_data["date"],
                "measurement": measurement,
                "attr_value": test_data["attr_value"],
                "link": test_data["link"].replace("\\\\\\", ""),
                "test_run_uuid": test_data["test_run_uuid"],
                "bug_links": test_data["bug_links"]
            });
        }

        // Fill table with remaining empty cells.
        for (index in table) {
            for (cnt in rows) {
                if (!(rows[cnt] in table[index])) {
                    table[index][rows[cnt]] = [];
                }
            }
        }

        data_table = '<table id="results_table_' + this.chart_id +
            '" class="inner-table">';

        table_head = '<thead><tr>';
        table_body = '<tbody><tr>';

        // Add table header, list of x-attributes/dates.
        for (index in table) {
	    // Row id with most fields in the table.
	    relevant_id = rows[0];
	    // Number of fields in that row.
	    max_same_date_size = 0;
            for (cnt in rows) {
                id = rows[cnt];
                if (table[index][id].length > max_same_date_size) {
		    relevant_id = id;
		    max_same_date_size = table[index][id].length;
                }
            }
            table[index]["max_size"] = max_same_date_size;
            for (var i=0; i < table[index][relevant_id].length; i++) {
                table_head += '<th>' + table[index][relevant_id][i]["date"].split(' ')[0] +
		    '</th>';
		if (has_xaxis_attribute) {
                    table_body += '<td>' + index + '</td>';
		}
            }
        }

        table_head += '</tr></thead>';
        table_body += '</tr><tr>';

        for (iter in rows) {
            id = rows[iter];

            for (index in table) {
                // Add "missing" cells.
                for (var i = 0; i < table[index]["max_size"]-table[index][id].length; i++) {
                    cls = "missing";
                    table_body += '<td class="' + cls + '">&mdash;</td>';
                }

                // Add regular cells.
                for (cnt in table[index][id]) {

                    // Calculate td class.
                    cell = table[index][id][cnt];
                    if (cell["pass"]) {
                        cls = "pass";
                    } else {
                        cls = "fail";
                    }
                    uuid = cell["test_run_uuid"];
                    relative_index_str = "";
                    if (cell["measurement"]) {
                        arr = cell["link"].split("/");
                        relative_index = arr[arr.length-2];
                        relative_index_str = 'data-relative_index="' + relative_index +'"';
                    }

                    table_body += '<td class="' + cls + '" data-chart-id="' +
                        this.chart_id + '" data-uuid="' + uuid + '" ' + relative_index_str + '>';

                    if (this.chart_data.basic.chart_type == "pass/fail") {
                        table_body += '<a target="_blank" href="' +
                            cell["link"] + '">' + cell["passes"] + '/' +
                            cell["total"] + '</a>';
                    } else if (this.chart_data.basic.chart_type == "measurement") {
                        if (isNumeric(cell["measurement"])) {
                            cell["measurement"] = cell["measurement"].toFixed(2);
                        }
                        table_body += '<a target="_blank" href="' +
                            cell["link"] + '">' +
                            cell["measurement"] + '</a>';
                    } else if (this.chart_data.basic.chart_type == "attributes") {
                        if (isNumeric(cell["attr_value"])) {
                            cell["attr_value"] = cell["attr_value"].toFixed(2);
                        }
                        table_body += '<a target="_blank" href="' +
                            cell["link"] + '">' + cell["attr_value"] + '</a>';
                    }

                    table_body += "</td>";
                }
            }
            table_body += '</tr><tr>';
        }

        table_body += '</tr></tbody>';
        $("#results-table_" + this.chart_id + " tbody").html(table_head +
                                                       table_body);
    }

    ChartQuery.prototype.set_dates = function() {
        // Populate range dropdowns.
        keys = this.get_keys();

        if (this.chart_data.basic.is_keys_numeric) {
            keys.sort(function(x,y) {return x-y;});
        } else {
            keys.sort();
        }

        for (i in keys) {
            $("#start_date_" + this.chart_id).append($("<option/>", {
                value: keys[i],
                text: keys[i]
            }));
            $("#end_date_" + this.chart_id).append($("<option/>", {
                value: keys[i],
                text: keys[i]
            }));
        }
        $("#end_date_" + this.chart_id + " option:last").attr("selected",
                                                              "selected");
    }

    ChartQuery.prototype.validate_build_number_selection = function() {
        // Validates start date field value against end data field value.
        // start date needs to be "less" then end date.

        start_number = $("#start_date_" + this.chart_id).val();
        if (isNumeric(start_number)) {
	    start_number = parseFloat(start_number);
        }
        end_number = $("#end_date_" + this.chart_id).val();
        if (isNumeric(end_number)) {
	    end_number = parseFloat(end_number);
        }

        if (start_number >= end_number) {
	    return false;
        } else {
            return true;
        }
    }

    ChartQuery.prototype.add_settings_events = function() {

        $("#start_date_"+this.chart_id).focus(function() {
            $(this).data('lastSelected', $(this).find('option:selected'));
        });
        $("#end_date_"+this.chart_id).focus(function() {
            $(this).data('lastSelected', $(this).find('option:selected'));
        });

        var chart = this;
        $("#start_date_"+this.chart_id).change(
            function() {
                if (!chart.validate_build_number_selection()) {
                    $(this).data("lastSelected").attr("selected", "selected");
                    validation_alert(chart.BUILD_NUMBER_ERROR);
                    return false;
                }
                chart.update_plot();
                chart.update_settings();
            }
        );

        $("#end_date_"+this.chart_id).change(
            function() {
                if (!chart.validate_build_number_selection()) {
                    $(this).data("lastSelected").attr("selected", "selected");
                    validation_alert(chart.BUILD_NUMBER_ERROR);
                    return false;
                }
                chart.update_plot();
            }
        );

        $("#is_legend_visible_"+this.chart_id).change(function() {
            chart.update_plot();
            chart.update_settings();
        });

        $("#is_delta_"+this.chart_id).change(function() {
            chart.update_plot();
            chart.update_settings();
        });

        $("#has_subscription_link_"+this.chart_id).click(function() {
            $("#has_subscription_" + chart.chart_id).val(
                $("#has_subscription_" + chart.chart_id).val() != "true");
            chart.update_settings();
        });
    }

    ChartQuery.prototype.apply_settings = function() {

        if (this.chart_data.user) { // Is authenticated.
            if (this.chart_data.user.start_date) {
                available_options = $.map($("#start_date_" + this.chart_id + " option"), function(e) { return e.value; });
                if (available_options.indexOf(this.chart_data.user.start_date) > -1) {
                    $("#start_date_" + this.chart_id).val(
                        this.chart_data.user.start_date);
                }
            }
            if (this.chart_data.user.is_legend_visible == false) {
                $("#is_legend_visible_" + this.chart_id).prop("checked",
                                                              false);
            }
            if (!this.chart_data.user.is_delta) {
                $("#is_delta_" + this.chart_id).prop("checked",
                                                     false);
            }

            this.set_subscription_link(this.chart_data.user.has_subscription);
        }
    }

    ChartQuery.prototype.update_settings = function() {

        url = "/results/chart/" + this.chart_data.basic.chart_name +
            "/" + this.chart_id + "/+settings-update";

        // Needed for callback function.
        var chart = this;
        $.ajax({
            url: url,
            type: "POST",
            data: {
                csrfmiddlewaretoken: csrf_token,
                start_date: $("#start_date_" + this.chart_id).val(),
                is_legend_visible: $("#is_legend_visible_" + this.chart_id).prop("checked"),
                is_delta: $("#is_delta_" + this.chart_id).prop("checked"),
            },
            success: function (data) {
                //chart.set_subscription_link(data[0].fields.has_subscription);
            },
        });
    }

    ChartQuery.prototype.set_subscription_link = function(subscribed) {

        if (this.chart_data["target_goal"] != null) {
            if (subscribed) {
                $("#has_subscription_"+this.chart_id).val(true);
                $("#has_subscription_link_"+this.chart_id).html(
                    "Unsubscribe from target goal");
            } else {
                $("#has_subscription_"+this.chart_id).val(false);
                $("#has_subscription_link_"+this.chart_id).html(
                    "Subscribe to target goal");
            }
        }
    }

    ChartQuery.prototype.update_urls = function() {
        canvas = $("#inner_container_" + this.chart_id + " > .flot-base").get(0);
        var dataURL = canvas.toDataURL();
        document.getElementById("chart_img_" + this.chart_id).href = dataURL;
    }

    ChartQuery.prototype.test_show_tick = function(tick) {
        // Test if the date/attribute used for ticks is between specified
        // number/date boundaries.
        start_number = $("#start_date_" + this.chart_id).val();
        end_number = $("#end_date_" + this.chart_id).val();
        if (this.chart_data.basic.is_keys_numeric) {
            tick = parseFloat(tick);
            start_number = parseFloat(start_number);
            end_number = parseFloat(end_number);
        }
        if (tick <= end_number && tick >= start_number) {
	    return true;
        }
        return false;
    }

    ChartQuery.prototype.update_plot = function() {

        // Init plot data.
        plot_data = {};

        for (iter in this.chart_data.data) {

	    row = this.chart_data.data[iter];
            if (!(row.id in plot_data)) {
                plot_data[row.id] = {
                    "alias": row.id.replace(/\\/g , ""),
                    "representation": this.chart_data.basic.representation,
                    "data": [],
                    "meta": [],
                    "labels": [],
                    "max": - Number.MAX_VALUE,
                    "min": Number.MAX_VALUE,
                    "sum": 0
                };
            }
        }

        // Dates on the x-axis.
        dates = [];

        // Get all build numbers to be used as tick labels.
        ticks = [];
        for (iter in this.chart_data.data) {

	    row = this.chart_data.data[iter];

            if (this.chart_data.basic.xaxis_attribute) {
                tick = row["attribute"];
            } else {
	        tick = row["date"].split('.')[0];
            }

            if (this.test_show_tick(tick)) {
	        if (!isNumeric(tick) && !this.chart_data.basic.xaxis_attribute) {
	            tick = format_date(tick);
	        }
                if (ticks.indexOf(tick) == -1) {
	            ticks.push(tick);
                }
            }
        }

        // Grid maximum and minimum values for y axis.
        var y_max = - Number.MAX_VALUE;
        var y_max_pass = - Number.MAX_VALUE;
        var y_min = Number.MAX_VALUE;

        for (iter in this.chart_data.data) {

	    row = this.chart_data.data[iter];

            if (this.chart_data.basic.xaxis_attribute) {
                if (row["attribute"]) {
                    tick = row["attribute"];
                } else {
                    continue;
                }
            } else {
                tick = row["date"].split(".")[0];
            }

            // If some of the items have numeric attribute, ignore
            // others which don't.
            if (this.chart_data.basic.is_keys_numeric && !isNumeric(tick)) {
                continue;
            }

            // Fix json escaping.
            row["link"] = row["link"].replace("\\\\\\", "");

            id = row["id"];
            if (this.test_show_tick(tick)) {

                // Current iterator for plot_data[id][data].
                iter = plot_data[id]["data"].length;

                tooltip = row["id"] + "<br>";
                if (this.chart_data.basic.chart_type == "pass/fail") {
                    if (this.chart_data.basic.is_percentage == true) {
                        value = row["percentage"];
                        tooltip += "Pass rate: " + value + "%";
                    } else {
                        value = row["passes"];
                        tooltip += "Pass: " + value + ", Total: " +
                            row["total"] + ", Skip: " + row["skip"];
                    }

                } else if (this.chart_data.basic.chart_type == "measurement") {
                    value = parseFloat(row["measurement"]);
                    if (isNaN(value)) {
                        // Ignore plot point where measurement is non-numeric.
                        continue;
                    }
                    tooltip += "Value: " + value;

                } else if (this.chart_data.basic.chart_type == "attributes") {
                    value = row["attr_value"];
                    tooltip += "Value: " + value;
                }

                tooltip += "<br>";
                label = "";

                // Calculate maximum passes.
                if (row["passes"] > y_max_pass) {
                    y_max_pass = row["passes"];
                }

                // Support metadata content with image and tooltip text.
                if (!$.isEmptyObject(row["metadata_content"])) {
                    label = "/static/dashboard_app/images/metadata.png";
                    for (key in row["metadata_content"]) {
                        tooltip += key + " changed to " +
                            row["metadata_content"][key][1] + "<br>";
                    }
                }

                // Support test result comments. Metadata display will have
                // priority over comments.
                if (row["comments"]) {
                    if (label == "") {
                        label = "/static/dashboard_app/images/icon-info.png";
                    }
                    if (this.chart_data.basic.chart_type == "pass/fail") {
                        tooltip += "Has comments<br>";
                    } else {
                        tooltip += row["comments"] + "<br>";
                    }
                }

                meta_item = {
		    "pk": row["pk"],
                    "link": row["link"],
                    "pass": row["pass"],
                    "tooltip": tooltip,
                };

                // Add the data.
                if (this.chart_data.basic.is_keys_numeric) {
                    insert_data_item(tick, [tick, value],
                                     plot_data[id]["data"]);
                    insert_data_item(tick, label,
                                     plot_data[id]["labels"]);
                    meta_key = tick + "_" +  value;
                    plot_data[id]["meta"][meta_key] = meta_item;

                } else if (this.chart_data.basic.xaxis_attribute) {
                    key = ticks.indexOf(row["attribute"]);
                    data_item = [key, value];
                    insert_data_item(key, [key, value],
                                     plot_data[id]["data"]);
                    insert_data_item(key, label,
                                     plot_data[id]["labels"]);
                    // Meta keys are made unique by concatination.
                    plot_data[id]["meta"][data_item.join("_")] =
                        meta_item;
                } else {
                    date = row["date"].split(".")[0].split(" ").join("T");
                    key = Date.parse(date);
                    dates.push(key);
                    data_item = [key, value];
                    plot_data[id]["data"].push(data_item);
                    plot_data[id]["labels"].push(label);
                    // Make meta keys are made unique by concatination.
                    plot_data[id]["meta"][data_item.join("_")] =
                        meta_item;
                }

                // Calculate max, min and avg for statistics.
                if (value < plot_data[id]["min"]) {
                    plot_data[id]["min"] = value;
                }
                if (value > plot_data[id]["max"]) {
                    plot_data[id]["max"] = value;
                }
                plot_data[id]["sum"] = plot_data[id]["sum"] + value;
            }
        }

        data = [];

        // Prepare data and additional drawing options in series.
        bar_alignement = ["left", "center", "right"];
        alignement_counter = 0;

        // Pack data in series for plot display.
        for (var id in plot_data) {

            // Delta reporting, calculate diferences.
            if ($("#is_delta_" + this.chart_id).prop("checked")) {
                var new_data = [];
                var new_meta_keys = [];
                var tooltips = [];
                for (j in plot_data[id]["data"]) {
                    if (j == 0) { //first element is auto-set to 0.
                        new_value = 0;
                        new_data.push(
                            plot_data[id]["data"][j].slice());
                        new_data[0][1] = new_value;

                    } else {
                        new_value = +parseFloat(plot_data[id]["data"][j][1] -
                                     plot_data[id]["data"][j-1][1]).toFixed(2);
                        new_data.push(
                            [plot_data[id]["data"][j][0],
                             new_value]);

                    }
                    // Set metadata key for first element.
                    var meta_key = plot_data[id]["data"][j][0]
                        + "_" + plot_data[id]["data"][j][1];
                    new_meta_keys[meta_key] = new_data[j][0] + "_" +
                        new_data[j][1];
                    tooltips[meta_key] =
                        plot_data[id]["meta"][meta_key]["tooltip"] + "Delta: " + new_value + "<br>";
                }
                plot_data[id]["data"] = new_data;

                // Need to update metadata keys as well.
                var new_metadata = [];
                for (j in plot_data[id]["meta"]) {
                    plot_data[id]["meta"][j]["tooltip"] =
                        tooltips[j];
                    new_metadata[new_meta_keys[j]] =
                        plot_data[id]["meta"][j];
                }
                plot_data[id]["meta"] = new_metadata;
            }

            if (Object.keys(this.legend_items).length != Object.keys(plot_data).length) {
                this.legend_items[id] = {
                    test_id: id,
                    dom_id: "legend_" + id,
                    min: plot_data[id]["min"],
                    max: plot_data[id]["max"],
                    avg: (plot_data[id]["sum"] / plot_data[id]["data"].length).toFixed(2),
                };
            }

	    if (this.legend_items[id].show == false) {
                bars_options = {show: false};
                lines_options = {show: false};
	        points_options = {show: false};
                plot_data[id]["labels"] = [];
            } else {

		points_options = {show: true};
		if (plot_data[id]["representation"] == "bars") {
                    if (alignement_counter++ > 2) {
			alignement_counter = 0;
                    }
                    bars_options = {
			show: true,
			align: bar_alignement[alignement_counter]
                    };
                    lines_options = {show: false};
		} else {
                    bars_options = {show: false};
                    lines_options = {show: true};
		}

		for (var i in plot_data[id]["data"]) {
                    if (plot_data[id]["data"][i][1] > y_max) {
			y_max = plot_data[id]["data"][i][1];
                    }
                    if (plot_data[id]["data"][i][1] < y_min) {
			y_min = plot_data[id]["data"][i][1];
                    }
		}
	    }

            data.push({
                label: plot_data[id]["alias"],
                showLabels: true,
                labels: plot_data[id]["labels"],
                labelPlacement: "above",
                canvasRender: true,
                data: plot_data[id]["data"],
                meta: plot_data[id]["meta"],
                bars: bars_options,
                lines: lines_options,
                points: points_options,
                test_id: id
            });
        }

        // Add target goal dashed line to the plot.
        if (this.chart_data.basic.target_goal != null) {
            if (this.chart_data.basic.is_percentage == true) {
                target_goal = parseFloat(this.chart_data["target_goal"]/y_max_pass).toFixed(4) * 100;
            } else {
                target_goal = this.chart_data["target_goal"];
            }

	    goal_data = [];

            if (this.chart_data.basic.is_keys_numeric || this.chart_data.basic.xaxis_attribute) {
	        for (var i in ticks) {
	            goal_data.push([ticks[i], target_goal]);
	        }
            } else {
	        for (key in dates) {
	            goal_data.push([dates[key], target_goal]);
	        }
            }

	    data.push({
                data: goal_data, dashes: {show: true},
                lines: {show: false}, points: { show: false }, color: "#999999"
            });
        }

        chart_width = $("#inner_container_" + this.chart_id).width();

        show_legend = true;
        if ($("#is_legend_visible_" + this.chart_id).prop("checked") == false) {
            $("#legend_container_" + this.chart_id).html("");
            $("#legend_container_" + this.chart_id).css("width", "0");
            $("#inner_container_" + this.chart_id).css("width", "98%");
            $("#dates_container_" + this.chart_id).css("width", "95%");
            $("#toggle_options_container_" + this.chart_id).css("width", "95%");
            show_legend = false;
        } else {
            $("#legend_container_" + this.chart_id).css("width", "15%");
            $("#inner_container_" + this.chart_id).css("width", "82%");
            $("#dates_container_" + this.chart_id).css("width", "80%");
            $("#toggle_options_container_" + this.chart_id).css("width", "80%");
        }

        y_label = "";
        if (this.chart_data["chart_type"] == "pass/fail") {
            y_label = "Pass/Fail";
        } else if (this.chart_data["chart_type"] == "measurement") {
            if (this.chart_data.data[0]) {
                y_label = this.chart_data.data[0].units;
            } else {
                y_label = "units";
            }
        }

        if (this.chart_data.basic.is_keys_numeric || this.chart_data.basic.xaxis_attribute) {

            chart_data = this.chart_data;
            tick_formatter = function(val, axis) {
                    if (chart_data.basic.is_keys_numeric) {
                        return val;
                    } else {
                        return ticks[val].replace(" ", "<br/>");
                    }
            }

            xaxis = {
                tickDecimals: (this.chart_data.is_keys_decimal)? 2:0,
                tickFormatter: tick_formatter,
            };

        } else {
            xaxis = {
                mode: "time",
                timeformat: "%d/%m/%Y<br/>%H:%m",
            };
        }

        var options = {
	    series: {
	        lines: { show: true },
	        points: { show: true },
                bars: { barWidth: 0.5 },
	    },
            grid: {
                hoverable: true,
                clickable: true,
            },
	    legend: {
	        show: show_legend,
	        position: "nw",
                //            margin: [chart_width-40, 0],
	        container: "#legend_container_" + this.chart_id,
	        labelFormatter: function(label, series) {
                    label_hidden = "<input type='hidden' " +
                        "id='legend_" + series.test_id + "' " +
                        "value='" + series.test_id + "'/>";
		    return label + label_hidden;
	        },
	    },
            xaxis: xaxis,
	    yaxis: {
	        tickDecimals: 0,
                axisLabel: y_label,
                axisLabelUseCanvas: true,
                axisLabelFontFamily: "Verdana",
            },
            canvas: true,
            zoom: {
                interactive: true
            },
            pan: {
                interactive: true
            },
        };

        // We cannot apply autoscaleMargin for y axis since y_max and y_min
        // are explicitely set. Therefore we will manually increase/decrease
        // the limits.
        y_max += (0.1 * Math.abs(y_max));
        y_min -= (0.1 * Math.abs(y_min));

        if (this.chart_data.basic.is_percentage == true) {
            options["yaxis"]["max"] = 110;
            options["yaxis"]["min"] = 0;
        } else {
            options["yaxis"]["max"] = y_max;
            options["yaxis"]["min"] = y_min;
        }

        this.plot = $.plot($("#outer_container_" + this.chart_id + " #inner_container_" + this.chart_id), data, options);

        // Setup hooks, events, tooltips and css in the legend.
        add_zoom_out(this);
        setup_clickable(this);
        setup_legend_tooltips(this);
        setup_legend_css(this);

        // Setup chart object reference.
        this.plot.chart = this;
        // Setup draw hook for plot.
        this.plot.hooks.draw.push(function(plot, canvascontext) {
            setup_clickable(plot.chart);
            setup_legend_tooltips(plot.chart);
            setup_legend_css(plot.chart);
        });

        this.plot.hooks.drawSeries.unshift(function(plot, canvascontext, series) {
            reset_images(series);
        });

    }

    reset_images = function(series) {
        for (i = 0; i < series.data.length; i++) {
            if (series.hasImage && series.hasImage[i]) {
                series.hasImage[i] = null;
            }
        }
    }

    setup_legend_tooltips = function(chart) {
        $("#legend_container_" + chart.chart_id + " td:last-child").each(function(index) {
            $(this).attr("data-toggle", "tooltip");
            $(this).attr("data-placement", "right");
            var title =
                "Min: " + chart.legend_items[$(this).text()].min +
                ", Max: " + chart.legend_items[$(this).text()].max +
                ", Avg: " + chart.legend_items[$(this).text()].avg;
            $(this).attr("title", title);
        });
    }

    setup_clickable = function(chart) {

        $("#legend_container_" + chart.chart_id + " table:first-child tbody tr").each(function(index) {

            $(this).click(function(e) {
                var show = chart.legend_items[$(this).text()].show;
		if (typeof(show) == "undefined") {
		    chart.legend_items[$(this).text()].show = false;
		} else {
                    chart.legend_items[$(this).text()].show = !show;
		}

                chart.update_plot();
            });
        });
    }

    setup_legend_css = function(chart) {

        for (var i in chart.legend_items) {
            if (chart.legend_items[i].show == true || typeof(chart.legend_items[i].show) == "undefined") {
                $("#" + chart.legend_items[i].dom_id).parent().css("color", "#545454");
            } else {
                $("#" + chart.legend_items[i].dom_id).parent().css("color", "#999");
            }
        }
    }

    add_zoom_out = function(chart) {

        $('<div class="zoom-out-button">zoom out</div>').click(
            function () {
                chart.plot.zoomOut();
            }).appendTo("#inner_container_" + chart.chart_id).css(
                "margin-left",
                parseInt($("#inner_container_" + chart.chart_id).children().first().css("width")) - 90 + "px");
    }

    isNumeric = function(n) {
        return !isNaN(parseFloat(n)) && isFinite(n);
    }

    is_array_numeric = function(arr) {
        // Check if all items in array are numeric.
        var is_array_numeric = true;
        for (iter in arr) {
            if (!isNumeric(arr[iter])) {
                is_array_numeric = false;
                break;
            }
        }
        return is_array_numeric;
    }

    is_any_element_decimal = function(arr) {
        // Check if any of the elements in array are decimal.
        var is_decimal = false;
        for (iter in arr) {
            if (arr[iter].indexOf(".") != -1) {
                is_decimal = true;
                break;
            }
        }
        return is_decimal;
    }

    isValidUrl = function(url) {
        return url.match(/^https?:\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>\#%"\,\{\}\\|\\\^\[\]`]+)?$/);
    }

    insert_data_item = function(key, value, data) {
        // Insert item at the sorted position in the data.
        // data represents list of two-value lists.
        if (data.length == 0 || parseFloat(key) <= parseFloat(data[0][0])) {
            data.splice(0, 0, value);
            return;
        }
        for (var i=0; i < data.length-1; i++) {
            if (parseFloat(key) > parseFloat(data[i][0]) &&
                parseFloat(key) <= parseFloat(data[i+1][0])) {
                data.splice(i+1, 0, value);
                return;
            }
        }
        data.splice(data.length, 0, value);
    }

    format_date = function(date_string) {
        time = date_string.split(' ')[1];
        date = $.datepicker.parseDate("yy-mm-dd", date_string);
        date_string = $.datepicker.formatDate("M d, yy", date);
        return date_string + "<br/>" + time;
    }

    fixHelperModified = function(element, tr) {
        var $originals = tr.children();
        var $helper = tr.clone();
        $helper.children().each(function(index) {
            $(this).width($originals.eq(index).width())
        });
        return $helper;
    };

    validation_alert = function(message) {
        bootbox.alert(message);
    }

    showTooltip = function(x, y, contents, pass) {
        bkg_color = (pass)? '#98c13d' : '#ff7f7f';
        $('<div id="tooltip">' + contents + '</div>').css({
            position: 'absolute', display: 'none', top: y + 5, left: x + 5,
            border: '1px solid #000', padding: '2px',
            'background-color': bkg_color, opacity: 0.80
        }).appendTo("body").fadeIn(200);
    }

    toggle_print_menu = function(e, chart_id) {
        $("#print_menu_" + chart_id).show();
        $("#print_menu_" + chart_id).offset({left: e.pageX-15, top: e.pageY-5});
    }

    toggle_item_menu = function(chart_id, pageX, pageY) {
        $("#item_menu_" + chart_id).show();
        $("#item_menu_" + chart_id).offset({left: pageX-15, top: pageY-5});
    }

    init_loading_dialog = function() {
    // Setup the loading image dialog.
        $("#main_container").append('<div id="loading_dialog"></div>');
        $("#loading_dialog").append('<img src="/static/dashboard_app/images/ajax-progress.gif" alt="Loading..." />');

        $('#loading_dialog').dialog({
            autoOpen: false,
            title: '',
            draggable: false,
            height: 45,
            width: 250,
            modal: true,
            resizable: false,
            dialogClass: 'loading-dialog'
        });

        $('.loading-dialog div.ui-dialog-titlebar').hide();
    }
    init_loading_dialog();

    chart = new Chart(chart_data);
    chart.start();

    //add_bug_link();

    $(window).resize(function () {
        chart.redraw();
    });

});
