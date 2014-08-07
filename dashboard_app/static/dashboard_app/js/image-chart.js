$(document).ready(function () {

    function ImageReport(chart_data) {
        this.chart_data = chart_data;
        this.charts = [];
    }

    ImageReport.prototype.start = function() {
        // Add charts.
        for (chart_id in this.chart_data) {
            chart = new ImageChart(chart_id, this.chart_data[chart_id]);
            chart.add_chart();
            this.charts.push(chart);
        }
    }

    ImageReport.prototype.redraw = function() {
        // Add charts.
        for (var i in this.charts) {
            this.charts[i].update_plot();
        }
    }

    function ImageChart(chart_id, chart_data) {
        this.plot = null;
        this.chart_id = chart_id;
        this.chart_data = chart_data;
        this.legend_items = [];
    }

    ImageChart.prototype.BUILD_NUMBER_ERROR =
        "End build number must be greater then the start build number.";

    ImageChart.prototype.setup_clickable = function() {

        var chart = this;
        $("#legend_container_" + this.chart_id + " table:first-child tbody tr").each(function(index) {

            $(this).click(function() {

                if (chart.legend_items[index].show == true) {
                    chart.legend_items[index].show = false;
                } else {
                    chart.legend_items[index].show = true;
                }

                chart.update_plot();
            });
        });
    }

    ImageChart.prototype.setup_legend_css = function() {

        for (var i in this.legend_items) {
            if (this.legend_items[i].show == true) {
                $("#" + this.legend_items[i].dom_id).parent().css("color", "#545454");
            } else {
                $("#" + this.legend_items[i].dom_id).parent().css("color", "#999");
            }
        }
    }

    ImageChart.prototype.add_chart = function() {

        if (this.chart_data.test_data) {
            // Add chart container.
            $("#main_container").append(
                '<div id="chart_container_'+ this.chart_id + '"></div>');
            // Add headline container.
            $("#chart_container_" + this.chart_id).append(
                '<div class="headline-container" id="headline_container_' +
                    this.chart_id + '"></div>');
            // Add filter links used.
            $("#chart_container_" + this.chart_id).append(
                '<div class="filter-links-container"' +
                    'id="filter_links_container_' + this.chart_id +
                    '"></div>');
            // Add data table link.
            $("#filter_links_container_" + this.chart_id).append(
                '<span class="table-link-container"' +
                    'id="table_link_container_' + this.chart_id + '"></span>');
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

            // Add headline and description.
            this.update_headline();
            // Add dates/build numbers.
            this.update_dates();
            // Add filter links.
            this.update_filter_links();
            // Add data tables.
            this.update_data_tables();
            // Generate chart.
            this.update_plot();
            // Add source for saving charts as images and csv export.
            this.update_urls();
            // Update events.
            this.update_events();
        }
    }

    ImageChart.prototype.setup_print_menu = function() {
        chart_id = this.chart_id;
        $("#print_menu_" + chart_id).menu();
        $("#print_menu_" + chart_id).hide();
        $("#print_menu_" + chart_id).mouseleave(function() {
            $("#print_menu_" + chart_id).hide();
        });
    }

    ImageChart.prototype.update_events = function() {

        // Bind plotclick event.
        $("#inner_container_" + this.chart_id).bind(
            "plotclick",
            function (event, pos, item) {
                if (item) {
                    // Make datapoint unique value
                    datapoint = item.datapoint.join("_");
                    url = window.location.protocol + "//" +
                        window.location.host +
                        item.series.meta[datapoint]["link"];
                    window.open(url, "_blank");
                }
            });

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


    ImageChart.prototype.update_headline = function() {
        $("#headline_container_" + this.chart_id).append(
            '<span class="chart-headline">' + this.chart_data["name"] +
                '</span>');
        $("#headline_container_" + this.chart_id).append(
            '<span>' + this.chart_data["description"] + '</span>');
    }

    ImageChart.prototype.update_filter_links = function() {

        $("#filter_links_container_" + this.chart_id).append(
            '<span style="margin-left: 30px;">Filters used:&nbsp;&nbsp;' +
                '</span>');
        filter_links = [];
        for (filter_id in this.chart_data.filters) {
            filter_links.push('<a href="' +
                              this.chart_data.filters[filter_id]["link"] +
                              '">~' +
                              this.chart_data.filters[filter_id]["owner"] +
                              '/' +
                              this.chart_data.filters[filter_id]["name"] +
                              '</a>');
        }
        filter_html = filter_links.join(", ");
        $("#filter_links_container_" + this.chart_id).append(
            '<span>' + filter_html + '</span>');

        $("#filter_links_container_" + this.chart_id).append(
            '<span class="chart-save-img">' +
                '<a id="chart_menu_' + this.chart_id + '"' +
                ' onclick="toggle_print_menu(event, ' + this.chart_id + ')">' +
                '<img src="' + image_url + 'icon-print.png"></a>' +
                '</span>');

        $("#filter_links_container_" + this.chart_id).append(
            '<ul class="print-menu" id="print_menu_' + this.chart_id + '">' +
                '<li class="print-menu-item"><a href="#" id="chart_csv_' +
                this.chart_id + '">' +
                'Download as CSV</a></li>' +
                '<li class="print-menu-item"><a target="_blank" href="#"' +
                ' id="chart_img_' + this.chart_id +
                '">View as image</a></li>' +
                '</ul>');

        this.setup_print_menu();
    }

    ImageChart.prototype.update_dates = function() {

        // Add dates(build number) fields and toggle legend checkbox.
        $("#dates_container_" + this.chart_id).append(
            '<span style="margin-left: 30px;">Start build number:&nbsp;' +
                '&nbsp;</span>');
        $("#dates_container_" + this.chart_id).append(
            '<span><select id="start_date_' + this.chart_id +
                '"></select></span>');
        $("#dates_container_" + this.chart_id).append(
            '<span>&nbsp;&nbsp;&nbsp;&nbsp;End build number:&nbsp;&nbsp;' +
                '</span>');
        $("#dates_container_" + this.chart_id).append(
            '<span><select id="end_date_' + this.chart_id + '"></select>' +
                '</span>');

        // Add percentages if chart type is pass/fail.
        if (this.chart_data["chart_type"] == "pass/fail") {
            $("#dates_container_" + this.chart_id).append(
                '<span>&nbsp;&nbsp;&nbsp;&nbsp;<label for="is_percentage_' +
                    this.chart_id +
                    '">Toggle percentage:</label>&nbsp;&nbsp;</span>');
            $("#dates_container_" + this.chart_id).append(
                '<span><input type="checkbox" id="is_percentage_' +
                    this.chart_id + '" /></span>');
        }

        $("#dates_container_" + this.chart_id).append(
            '<span>&nbsp;&nbsp;&nbsp;&nbsp;<label for="is_legend_visible_' +
                this.chart_id + '">Toggle legend:</label>&nbsp;&nbsp;</span>');
        $("#dates_container_" + this.chart_id).append(
            '<span><input type="checkbox" id="is_legend_visible_' +
                this.chart_id + '" checked="checked"/></span>');
        $("#dates_container_" + this.chart_id).append(
            '<span style="float: right;"><input id="has_subscription_' +
                this.chart_id +
                '" type="hidden"/><a id="has_subscription_link_' +
                this.chart_id + '" href="javascript:void(0)"></a></span>');

        this.set_dates();
        this.apply_settings();
        this.add_settings_events();
    }

    ImageChart.prototype.update_data_tables = function() {

        // Add dialog.
        $("#main_container").append('<div id="data_table_dialog_' +
                                    this.chart_id + '"></div>');

        // Init dialog.
        $('#data_table_dialog_' + this.chart_id).dialog({
            autoOpen: false,
            title: 'View data table',
            draggable: false,
            height: 280,
            width: 950,
            modal: true,
            resizable: false,
            open: function (event, ui) {
                $('#data_table_dialog_' + this.chart_id).css('overflow',
                                                             'hidden');

                $('.scroller').each(function() {
                    $(this).scrollLeft($(this)[0].scrollWidth);
                });
            }
        });

        // Add skeleton data to dialog.
        $("#data_table_dialog_" + this.chart_id).append(
            '<table id="outer-table"><tr><td>' +
                '<table id="test-run-names_' + this.chart_id +
                '" class="inner-table"><thead>' +
                '<tr><th>Build Number</th></tr>' +
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
                '" href="javascript:void(0)">View data table</a>');

        var chart = this;
        $("#data_table_link_" + this.chart_id).click(function(){
            $('#data_table_dialog_' + chart.chart_id).dialog("open");
        });
    }

    ImageChart.prototype.add_table_data = function() {

        // Create row headlines.
        table_rows = "<tr><td>Date</td></tr>";

        // Array with row names.
        rows = [];
        // Array with column strings
        columns = [];
        // Inner table data.
        table = {};

        // Create inner table with row names.
        for (iter in this.chart_data.test_data) {

            test_data = this.chart_data.test_data[iter];
            if ($.inArray(test_data["test_filter_id"], rows) == -1) {
                // Add unique rows and create row headlines HTML.

                rows.push(test_data["test_filter_id"]);

                test_name = test_data["alias"];
                if (test_name.length > 10) {
                    test_name = test_name.substring(0,10) + "...";
                }
                table_rows += "<tr><td title='" + test_data["alias"] +
                    "'>" + test_name + "</td></tr>";
            }
        }
        $("#test-run-names_" + this.chart_id + " tbody").html(table_rows);

        // Create column headlines.
        result_table_head = "<tr>";

        // Organize data in the 'table' multi array.
        for (iter in this.chart_data.test_data) {
            test_data = this.chart_data.test_data[iter];

            number = test_data["number"].split(' ')[0];
            if (!(number in table)) {
                table[number] = {};
            }

            if (!(test_data["test_filter_id"] in table[number])) {
                table[number][test_data["test_filter_id"]] = [];
            }

            table[number][test_data["test_filter_id"]].push({
                "passes": test_data["passes"],
                "total": test_data["total"],
                "measurement": test_data["measurement"],
                "link": test_data["link"],
                "test_run_uuid": test_data["test_run_uuid"],
                "bug_links": test_data["bug_links"]
            });
        }

        // Fill table with remaining empty filters.
        for (number in table) {
            for (cnt in rows) {
                if (!(rows[cnt] in table[number])) {
                    table[number][rows[cnt]] = [];
                }
            }
        }

        data_table = '<table id="results_table_' + this.chart_id +
            '" class="inner-table">';

        table_head = '<thead><tr>';
        table_body = '<tbody><tr>';

        // Add table header, list of build numbers/dates.
        for (number in table) {
            max_same_date_size = 0;
            for (cnt in rows) {

                filter_id = rows[cnt];
                if (table[number][filter_id].length > max_same_date_size) {
                    max_same_date_size = table[number][filter_id].length;
                }
            }
            table[number]["max_size"] = max_same_date_size;
            table[number]["date"] = test_data["date"];
            for (var i = 0; i < max_same_date_size; i++) {
                table_head += '<th>' + number + '</th>';
                table_body += '<td>' + number + '</td>';
            }
        }

        table_head += '</tr></thead>';
        table_body += '</tr><tr>';

        for (iter in rows) {
            filter_id = rows[iter];

            for (number in table) {
                // Add "missing" cells.
                for (var i = 0; i < table[number]["max_size"]-table[number][filter_id].length; i++) {
                    cls = "missing";
                    table_body += '<td class="' + cls + '">&mdash;</td>';
                }

                // Add regular cells.
                for (cnt in table[number][filter_id]) {

                    // Calculate td class.
                    cell = table[number][filter_id][cnt];
                    if (cell["passes"] < cell["total"]) {
                        cls = "fail";
                    } else {
                        cls = "pass";
                    }
                    uuid = cell["test_run_uuid"];
                    relative_index_str = "";
                    if (cell["measurement"]) {
                        arr = cell["link"].split("/")
                        relative_index = arr[arr.length-2]
                        relative_index_str = 'data-relative_index="' + relative_index +'"'
                    }

                    table_body += '<td class="' + cls + '" data-chart-id="' +
                        this.chart_id + '" data-uuid="' + uuid + '" ' + relative_index_str + '>';

                    if (this.chart_data["chart_type"] == "pass/fail") {
                        table_body += '<a target="_blank" href="' +
                            cell["link"] + '">' + cell["passes"] + '/' +
                            cell["total"] + '</a>';
                    } else {
                        table_body += '<a target="_blank" href="' +
                            cell["link"] + '">' + cell["measurement"] + '</a>';
                    }

                    table_body += '<span class="bug-link-container">' +
                        '<a href="#" class="add-bug-link"> [' +
                        cell["bug_links"].length + ']</a></span>';
                    table_body += '<span class="bug-links" ' +
                        'style="display: none">';

                    for (bug_link in cell["bug_links"]) {
                        bug = cell["bug_links"];
                        table_body += '<li class="bug-link">' + bug[bug_link] +
                            '</li>';
                    }

                    table_body += '</span>';
                    table_body += "</td>";
                }
            }
            table_body += '</tr><tr>';
        }

        table_body += '</tr></tbody>';
        $("#results-table_" + this.chart_id + " tbody").html(table_head +
                                                       table_body);

        this.update_tooltips();
    }

    ImageChart.prototype.update_tooltips = function() {
        // Update tooltips on the remaining td's for the test names.
        $(document).tooltip({items: "td"});
    }

    ImageChart.prototype.set_dates = function() {
        // Populate date dropdowns.
        dates = [];
        for (iter in this.chart_data.test_data) {
            item = this.chart_data.test_data[iter]["number"].split('.')[0];
            if (dates.indexOf(item) == -1) {
                dates.push(item);
            }
        }

        if (this.chart_data.has_build_numbers) {
            dates.sort(function(x,y) {return x-y;});
        } else {
            dates.sort();
        }

        for (i in dates) {
            $("#start_date_" + this.chart_id).append($("<option/>", {
                value: dates[i],
                text: dates[i]
            }));
            $("#end_date_" + this.chart_id).append($("<option/>", {
                value: dates[i],
                text: dates[i]
            }));
        }
        $("#end_date_" + this.chart_id + " option:last").attr("selected",
                                                              "selected");
    }

    ImageChart.prototype.validate_build_number_selection = function() {

        start_number = $("#start_date_" + this.chart_id).val();
        if (isNumeric(start_number)) {
	    start_number = parseInt(start_number);
        }
        end_number = $("#end_date_" + this.chart_id).val();
        if (isNumeric(end_number)) {
	    end_number = parseInt(end_number);
        }

        if (start_number >= end_number) {
	    return false;
        } else {
            return true;
        }
    }

    ImageChart.prototype.add_settings_events = function() {

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

        if (this.chart_data["chart_type"] == "pass/fail") {
            $("#is_percentage_"+this.chart_id).change(function() {
                chart.update_plot();
            });
        }

        $("#has_subscription_link_"+this.chart_id).click(function() {
            $("#has_subscription_" + chart.chart_id).val(
                $("#has_subscription_" + chart.chart_id).val() != "true");
            chart.update_settings();
        });
    }

    ImageChart.prototype.apply_settings = function() {

        if (this.chart_data.user) { // Is authenticated.
            if (this.chart_data.user.start_date) {
                $("#start_date_" + this.chart_id).val(
                    this.chart_data.user.start_date);
            }
            if (this.chart_data.user.is_legend_visible == false) {
                $("#is_legend_visible_" + this.chart_id).prop("checked",
                                                              false);
            }

            this.set_subscription_link(this.chart_data.user.has_subscription);
        }
    }

    ImageChart.prototype.update_settings = function() {

        url = "/dashboard/image-charts/" + this.chart_data["report_name"] +
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
                has_subscription: $("#has_subscription_" + this.chart_id).val(),
            },
            success: function (data) {
                chart.set_subscription_link(data[0].fields.has_subscription);
            },
        });
    }

    ImageChart.prototype.set_subscription_link = function(subscribed) {

        if (this.chart_data["target_goal"]) {
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

    ImageChart.prototype.update_urls = function() {
        canvas = $("#inner_container_" + this.chart_id + " > .flot-base").get(0);
        var dataURL = canvas.toDataURL();
        document.getElementById("chart_img_" + this.chart_id).href = dataURL;
        export_url = "/dashboard/image-charts/" +
            this.chart_data["report_name"] + "/" + this.chart_id + "/+export";
        document.getElementById("chart_csv_" + this.chart_id).href = export_url;
    }

    ImageChart.prototype.test_build_number = function(build_number) {

        // Test if the build number/date is between specified
        // number/date boundaries.
        start_number = $("#start_date_" + this.chart_id).val();
        end_number = $("#end_date_" + this.chart_id).val();
        if (this.chart_data.has_build_numbers) {
            build_number = parseInt(build_number);
            start_number = parseInt(start_number);
            end_number = parseInt(end_number);
        }
        if (build_number <= end_number && build_number >= start_number) {
	    return true;
        }
        return false;
    }

    ImageChart.prototype.update_plot = function() {

        // Init plot data.
        plot_data = {};

        for (iter in this.chart_data.test_data) {

	    row = this.chart_data.test_data[iter];
	    test_filter_id = row["test_filter_id"];
            if (!(test_filter_id in plot_data)) {
                plot_data[test_filter_id] = {
                    "alias": row["alias"],
                    "representation": row["filter_rep"],
                    "data": [],
                    "meta": [],
                    "labels": []
                };
            }
        }

        // Dates on the x-axis.
        dates = [];
        // Store all build numbers
        build_numbers = [];

        for (iter in this.chart_data.test_data) {

	    row = this.chart_data.test_data[iter];
            build_number = row["number"].split(".")[0];

            // If some of the filters have build_number_attribute, ignore
            // others which don't.
            if (this.chart_data.has_build_numbers && !isNumeric(build_number)) {
                continue;
            }

            test_filter_id = row["test_filter_id"];
            if (this.test_build_number(build_number)) {

                // Current iterator for plot_data[iter][data].
                iter = plot_data[test_filter_id]["data"].length;

                if (this.chart_data["chart_type"] == "pass/fail") {
                    if ($("#is_percentage_" + this.chart_id).prop("checked") == true) {
                        value = parseFloat(row["passes"]/row["total"]).toFixed(4) * 100;
                        tooltip = "Pass rate: " + value + "%";
                    } else {
                        value = row["passes"];
                        tooltip = "Pass: " + value + ", Total: " +
                            row["total"];
                    }

                } else {
                    value = row["measurement"];
                    tooltip = "Value: " + value;
                }

                tooltip += "<br>";
                label = "";

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
                    if (this.chart_data["chart_type"] == "pass/fail") {
                        tooltip += "Has comments<br>";
                    } else {
                        tooltip += row["comments"] + "<br>";
                    }
                }

                meta_item = {
                    "link": row["link"],
                    "pass": row["pass"],
                    "tooltip": tooltip,
                };

                if (this.chart_data.has_build_numbers) {
                    insert_data_item(build_number, [build_number, value],
                                     plot_data[test_filter_id]["data"]);
                    insert_data_item(build_number, label,
                                     plot_data[test_filter_id]["labels"]);
                    meta_key = build_number + "_" +  value;
                    plot_data[test_filter_id]["meta"][meta_key] = meta_item;
                    build_numbers.push(build_number);

                } else {
                    date = row["date"].split(".")[0].split(" ").join("T");
                    key = Date.parse(date);
                    dates.push(key);
                    data_item = [key, value];
                    plot_data[test_filter_id]["data"].push(data_item);
                    plot_data[test_filter_id]["labels"].push(label);
                    // Make meta keys are made unique by concatination.
                    plot_data[test_filter_id]["meta"][data_item.join("_")] =
                        meta_item;
                }
            }
        }

        data = [];

        // Prepare data and additional drawing options in series.
        bar_alignement = ["left", "center", "right"];
        alignement_counter = 0;

        filter_ids = Object.keys(plot_data);

        // Sort filters by alias.
        sorted_filter_ids = [];
        for (var i=0; i<filter_ids.length; i++) {
            filter_id = filter_ids[i];
            if (sorted_filter_ids.length == 0) {
                sorted_filter_ids.push(filter_id);
                continue;
            }
            for (var j=0; j<sorted_filter_ids.length; j++) {
                sorted_filter_id = sorted_filter_ids[j];

                if (plot_data[filter_id]["alias"] < plot_data[sorted_filter_id]["alias"]) {
                    sorted_filter_ids.splice(0, 0, filter_id);
                    break;
                }

                if (sorted_filter_ids[j+1] == null) {
                    sorted_filter_ids.push(filter_id);
                    break;
                } else {
                    next_sorted_filter_id = sorted_filter_ids[j+1];
                }

                if (plot_data[filter_id]["alias"] > plot_data[sorted_filter_id]["alias"] && plot_data[filter_id]["alias"] <= plot_data[next_sorted_filter_id]["alias"]) {
                    sorted_filter_ids.splice(j+1, 0, filter_id);
                    break;
                }
            }
        }

        // Grid maximum and minimum values for y axis.
        var y_max = - Number.MAX_VALUE;
        var y_min = Number.MAX_VALUE;

        // Pack data in series for plot display.
        for (var i in sorted_filter_ids) {
            test_filter_id = sorted_filter_ids[i];

            if (this.legend_items.length != sorted_filter_ids.length) {
                this.legend_items.push({
                    filter_id: test_filter_id,
                    dom_id: "legend_" + test_filter_id,
                    show: true,
                });
            }

            if (this.legend_items[i].show == false) {
                bars_options = {show: false};
                lines_options = {show: false};
	        points_options = {show: false};
                plot_data[test_filter_id]["labels"] = [];
            } else {
                points_options = {show: true};
                if (plot_data[test_filter_id]["representation"] == "bars") {
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

                for (var i in plot_data[test_filter_id]["data"]) {
                    if (plot_data[test_filter_id]["data"][i][1] > y_max) {
                        y_max = plot_data[test_filter_id]["data"][i][1];
                    }
                    if (plot_data[test_filter_id]["data"][i][1] < y_min) {
                        y_min = plot_data[test_filter_id]["data"][i][1];
                    }
                }
            }

            data.push({
                label: plot_data[test_filter_id]["alias"],
                showLabels: true,
                labels: plot_data[test_filter_id]["labels"],
                labelPlacement: "above",
                canvasRender: true,
                data: plot_data[test_filter_id]["data"],
                meta: plot_data[test_filter_id]["meta"],
                bars: bars_options,
                lines: lines_options,
                points: points_options,
                test_filter_id: test_filter_id,
            });
        }

        // Get all build numbers to be used as tick labels.
        build_numbers = [];
        for (iter in this.chart_data.test_data) {

	    row = this.chart_data.test_data[iter];

	    build_number = row["number"].split('.')[0];

            if (this.test_build_number(build_number)) {

	        if (!isNumeric(build_number)) {
	            build_number = format_date(build_number);
	        }
                if (build_numbers.indexOf(build_number) == -1) {
	            build_numbers.push(build_number);
                }
            }
        }

        // Add target goal dashed line to the plot.
        if (this.chart_data["target_goal"]) {
	    goal_data = [];

            if (this.chart_data.has_build_numbers) {
	        for (var i in build_numbers) {
	            goal_data.push([build_numbers[i],
                                    this.chart_data["target_goal"]]);
	        }
            } else {
	        for (key in dates) {
	            goal_data.push([dates[key], this.chart_data["target_goal"]]);
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
            $("#filter_links_container_" + this.chart_id).css("width", "95%");
            show_legend = false;
        } else {
            $("#legend_container_" + this.chart_id).css("width", "15%");
            $("#inner_container_" + this.chart_id).css("width", "82%");
            $("#dates_container_" + this.chart_id).css("width", "80%");
            $("#filter_links_container_" + this.chart_id).css("width", "80%");
        }

        y_label = "Pass/Fail";
        if (this.chart_data["chart_type"] != "pass/fail") {
            if (this.chart_data.test_data[0]) {
                y_label = this.chart_data.test_data[0].units;
            } else {
                y_label = "units";
            }
        }

        if (this.chart_data.has_build_numbers) {

            chart_data = this.chart_data;
            tick_formatter = function(val, axis) {
                    if (chart_data.has_build_numbers) {
                        return val;
                    } else {
                        return build_numbers[val];
                    }
            }

            xaxis = {
                tickDecimals: 0,
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
                        "id='legend_" + series.test_filter_id + "' " +
                        "value='" + series.test_filter_id + "'/>";
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
        };

        // We cannot apply autoscaleMargin for y axis since y_max and y_min
        // are explicitely set. Therefore we will manually increase/decrease
        // the limits.
        y_max *= 1.1;
        y_min *= 0.9;

        if ($("#is_percentage_" + this.chart_id).prop("checked") == true) {
            options["yaxis"]["max"] = 105;
            options["yaxis"]["min"] = 0;
        } else {
            options["yaxis"]["max"] = y_max;
            options["yaxis"]["min"] = y_min;
        }

        this.plot = $.plot($("#outer_container_" + this.chart_id + " #inner_container_" + this.chart_id), data, options);

        // Setup click events and css in the legend.
        this.setup_clickable();
        this.setup_legend_css();
    }

    isNumeric = function(n) {
        return !isNaN(parseFloat(n)) && isFinite(n);
    }

    isValidUrl = function(url) {
        return url.match(/^https?:\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>\#%"\,\{\}\\|\\\^\[\]`]+)?$/);
    }

    insert_data_item = function(key, value, data) {
        // Insert item at the sorted position in the data.
        // data represents list of two-value lists.
        if (data.length == 0 || parseInt(key) <= parseInt(data[0][0])) {
            data.splice(0, 0, value);
            return;
        }
        for (var i=0; i < data.length-1; i++) {
            if (parseInt(key) > parseInt(data[i][0]) &&
                parseInt(key) <= parseInt(data[i+1][0])) {
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
        alert(message);
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
        $("#print_menu_" + chart_id).offset({left: e.pageX, top: e.pageY});
    }

    add_bug_link = function () {
        var current_bug = [];

        $("#add-bug-dialog").bind('submit', function(e) {
            var bug_url = $("#add-bug-dialog").find('input[name=bug_link]').val();
            if (!isValidUrl(bug_url)) {
                e.preventDefault();
                alert("'" + bug_url + "' is not a valid url!!");
            }
            if (current_bug.indexOf(bug_url) > -1) {
                e.preventDefault();
                alert("'" + bug_url + "' is already linked!!");
            }
        });

        _submit = function () {
            $(this).submit();
        }

        var add_bug_dialog = $('#add-bug-dialog').dialog(
            {
                autoOpen: false,
                buttons: {'Cancel': function () {$(this).dialog('close');}, 'OK': _submit },
                modal: true,
                title: "Link bug to XXX"
            });

        get_testrun_and_buildnumber = function (element) {
            var cell = element.closest('td');
            var row = cell.closest('tr');
            var testrun = $($("#test-run-names_"+chart_id+" > tbody > tr")[row.index()]).text();
            var header_cells = element.closest('table').find('thead > tr > th');
            var buildnumber = $(header_cells[cell.index()]).text();
            return {testrun: $.trim(testrun), buildnumber: $.trim(buildnumber)};
        }

        find_previous_bugs = function (element) {
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

        get_linked_bugs = function (element) {
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
                var rel_idx = $(this).closest('td').data('relative_index');
                var chart_id = $(this).closest('td').data('chart-id');
                var back_url = add_bug_dialog.find('input[name=back]').val().split('?')[0] + '?bug_links_chart_id=' + chart_id;

                current_bug = get_linked_bugs($(this));
                add_bug_dialog.find('input[name=back]').val(back_url);
                add_bug_dialog.find('input[name=bug_link]').val('');
                add_bug_dialog.find('input[name=uuid]').val(uuid);

                if (rel_idx) {
                    add_bug_dialog.find('input[name=relative_index]').val(rel_idx);
                    link_bug_url = testresult_link_bug_url
                    unlink_bug_url = testresult_unlink_bug_url
                } else {
                    link_bug_url = testrun_link_bug_url
                    unlink_bug_url = testrun_unlink_bug_url
                }

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
                                $('#add-bug-dialog').attr('action', unlink_bug_url);
                                add_bug_dialog.find('input[name=bug_link]').val(bug);
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
                                $('#add-bug-dialog').attr('action', link_bug_url);
                                add_bug_dialog.find('input[name=bug_link]').val(bug);
                                add_bug_dialog.submit();
                            }
                        });
                } else {
                    prev_div.hide();
                }

                var title = "Link a bug to the '" + names.testrun +
                    "' run of build " + names.buildnumber;
                $('#add-bug-dialog').attr('action', link_bug_url);
                add_bug_dialog.dialog('option', 'title', title);
                add_bug_dialog.dialog('open');
            }
        );
    }

    report = new ImageReport(chart_data);
    report.start();

    add_bug_link();

    if (buglinks_chartid.length) {
        $('#data_table_link_' + buglinks_chartid).click();
    }

    $(window).resize(function () {
        report.redraw();
    });

});
