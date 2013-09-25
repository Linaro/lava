$(document).ready(function () {

    add_chart = function(chart_id, chart_data) {

        if (chart_data.test_data) {
            // Add chart container.
            $("#main_container").append(
                '<div id="chart_container_'+ chart_id + '"></div>');
            // Add headline container.
            $("#chart_container_" + chart_id).append(
                '<div class="headline-container" id="headline_container_' +
                    chart_id + '"></div>');
            // Add filter links used.
            $("#chart_container_" + chart_id).append(
                '<div class="filter-links-container" id="filter_links_container_' + chart_id + '"></div>');
            // Add dates/build numbers container.
            $("#chart_container_" + chart_id).append(
                '<div class="dates-container" id="dates_container_' +
                    chart_id + '"></div>');
            // Add outer plot container.
            $("#chart_container_" + chart_id).append(
                '<div class="outer-chart" id="outer_container_' +
                    chart_id + '"></div>');
            // Add inner plot container.
            $("#outer_container_" + chart_id).append(
                '<div class="inner-chart" id="inner_container_' +
                    chart_id + '"></div>');
            // Add legend container.
            $("#outer_container_" + chart_id).append(
                '<div class="legend" id="legend_container_' +
                    chart_id + '"></div>');

            // Add headline and description.
            update_headline(chart_id, chart_data);
            // Add dates/build numbers.
            update_dates(chart_id, chart_data);
            // Add filter links.
            update_filter_links(chart_id, chart_data);
            // Generate chart.
            update_plot(chart_id, chart_data);
            // Add source for saving charts as images.
            update_img(chart_id);
            // Update events.
            if (chart_data["is_interactive"]) {
                update_events(chart_id);
            }
        }
    }

    setup_sortable = function() {
        // Set up sortable plugin.
        $("#main_container").sortable({
            axis: "y",
            cursor: "move",
            placeholder: "sortable-placeholder",
            scroll: true,
            scrollSensitivity: 50,
            tolerance: "pointer",
        });
        $("#main_container").disableSelection();
    }

    update_events = function(chart_id) {
        // Bind plotclick event.
        $("#inner_container_"+chart_id).bind(
            "plotclick",
            function (event, pos, item) {
                if (item) {
                    url = window.location.protocol + "//" +
                        window.location.host +
                        item.series.meta[item.dataIndex]["link"];
                    window.open(url, "_blank");
                }
            });

        $("#inner_container_"+chart_id).bind(
            "plothover",
            function (event, pos, item) {
                $("#tooltip").remove();
                if (item) {
                    tooltip = item.series.meta[item.dataIndex]["tooltip"];
                    showTooltip(item.pageX, item.pageY, tooltip,
                                item.series.meta[item.dataIndex]["pass"]);
                }
            });
    }

    showTooltip = function(x, y, contents, pass) {
        bkg_color = (pass)? '#98c13d' : '#ff7f7f';
        $('<div id="tooltip">' + contents + '</div>').css({
            position: 'absolute', display: 'none', top: y + 5, left: x + 5,
            border: '1px solid #000', padding: '2px',
            'background-color': bkg_color, opacity: 0.80
        }).appendTo("body").fadeIn(200);
    }

    update_headline = function(chart_id, chart_data) {
        $("#headline_container_" + chart_id).append(
            '<span class="chart-headline">' + chart_data["name"] + '</span>');
        $("#headline_container_" + chart_id).append(
            '<span>' + chart_data["description"] + '</span>');
    }

    update_filter_links = function(chart_id, chart_data) {

        $("#filter_links_container_" + chart_id).append(
            '<span style="margin-left: 30px;">Filters used:&nbsp;&nbsp;</span>');
        filter_links = [];
        for (filter_id in chart_data.filters) {
            filter_links.push('<a href="' +
                              chart_data.filters[filter_id]["link"] + '">~' +
                              chart_data.filters[filter_id]["owner"] + '/' +
                              chart_data.filters[filter_id]["name"] +
                              '</a>');
        }
        filter_html = filter_links.join(", ");
        $("#filter_links_container_" + chart_id).append(
            '<span>' + filter_html + '</span>');

        $("#filter_links_container_" + chart_id).append(
            '<span class="chart-save-img">' +
                '<a target="_blank" href=# id="chart_img_' + chart_id +
                '"><img alt="Click to view as image"></a>' +
                '</span>');
    }

    update_dates = function(chart_id, chart_data) {
        $("#dates_container_" + chart_id).append(
            '<span style="margin-left: 30px;">Start build number:&nbsp;&nbsp;</span>');
        $("#dates_container_" + chart_id).append(
            '<span><select><option value="2013-09-02">2013-09-02</option></select></span>');
        $("#dates_container_" + chart_id).append(
            '<span>&nbsp;&nbsp;&nbsp;&nbsp;End build number:&nbsp;&nbsp;</span>');
        $("#dates_container_" + chart_id).append(
            '<span><select><option value="2013-09-02">2013-09-02</option></select></span>');
        $("#dates_container_" + chart_id).append(
            '<span style="float: right;"><a href="#">Subscribe to target goal</></span>');
    }

    update_img = function(chart_id) {
        canvas = $("#inner_container_" + chart_id + " > .flot-base").get(0);
        var dataURL = canvas.toDataURL();
        document.getElementById("chart_img_" + chart_id).href = dataURL;
    }

    update_plot = function(chart_id, chart_data) {

        // Get the plot data.
        plot_data = {};

        // Maximum number of test runs.
        max_iter = 0;

        for (test_id in chart_data.test_data) {
            // TODO: alias can't be the key in this array,
            // it's not unique accross multiple or the same filters.
            // Ensure that aliases are unique per chart.
	    row = chart_data.test_data[test_id];
            if (!(row["alias"] in plot_data)) {
                plot_data[row["alias"]] = {};
                plot_data[row["alias"]]["representation"] = row["filter_rep"];
                plot_data[row["alias"]]["data"] = [];
                plot_data[row["alias"]]["meta"] = [];
            }

            // Current iterator for plot_data[test_alias][data].
            iter = plot_data[row["alias"]]["data"].length;

            if (chart_data["chart_type"] == "pass/fail") {
                value = row["passes"];
                tooltip = "Pass: " + value + ", Total: " + row["total"];

            } else {
                value = row["measurement"];
                tooltip = "Value: " + value;
            }
	    plot_data[row["alias"]]["data"].push([iter, value]);
	    plot_data[row["alias"]]["meta"].push({
                "link": row["link"],
                "pass": row["pass"],
                "tooltip": tooltip,
            });

            if (iter > max_iter) {
                max_iter = iter;
            }
        }

        data = [];

        // Prepare data and additional drawing options in series.
        for (label in plot_data) {
            if (plot_data[label]["representation"] == "bars") {
                bars_options = {show: true};
                lines_options = {show: false};
            } else {
                bars_options = {show: false};
                lines_options = {show: true};
            }

            data.push({
                label: label,
                data: plot_data[label]["data"],
                meta: plot_data[label]["meta"],
                bars: bars_options,
                lines: lines_options,
            });
        }

        // Add target goal dashed line to the plot.
        if (chart_data["target_goal"]) {
	    goal_data = [];
	    for (iter = 0; iter <= max_iter; iter++) {
	        goal_data.push([iter, chart_data["target_goal"]]);
	    }

	    data.push({
                data: goal_data, dashes: {show: true},
                lines: {show: false}, color: "#000000"
            });
        }

        // Get all build numbers to be used as tick labels.
        build_numbers = [];
        for (test_id in chart_data.test_data) {

	    row = chart_data.test_data[test_id];

	    build_number = row["number"].split(' ')[0];
	    if (!isNumeric(build_number)) {
	        build_number = format_date(build_number);
	    }
	    build_numbers.push(build_number);
        }

        chart_width = $("#inner_container_" + chart_id).width();
        var options = {
	    series: {
	        lines: { show: true },
	        points: { show: false },
                bars: { barWidth: 0.5 },
	    },
            grid: {
                hoverable: true,
                clickable: true,
            },
	    legend: {
	        show: true,
	        position: "nw",
                //            margin: [chart_width-40, 0],
	        container: "#legend_container_" + chart_id,
	        labelFormatter: function(label, series) {
		    if (label.length > 25) {
		        return label.substring(0,24) + "...";
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
                labelWidth: 25,
	    },
            canvas: true,
        };

        $.plot($("#outer_container_" + chart_id + " #inner_container_" + chart_id),
               data, options);
    }

    isNumeric = function(n) {
        return !isNaN(parseFloat(n)) && isFinite(n);
    }

    format_date = function(date_string) {
        date = $.datepicker.parseDate("yy-mm-dd", date_string);
        date_string = $.datepicker.formatDate("M d, yy", date);
        return date_string;
    }

    // Add charts.
    for (chart_id in chart_data) {
        add_chart(chart_id, chart_data[chart_id]);
    }

    setup_sortable();
});
