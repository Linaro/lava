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
            update_plot(chart_id, chart_data, null);
            // Add source for saving charts as images and csv export.
            update_urls(chart_id, chart_data["report_name"]);
            // Update events.
            update_events(chart_id);
        }
    }

    setup_sortable = function(chart_id, chart_data) {

        $("#legend_container_" + chart_id + " table:first-child tbody").sortable({
            axis: "y",
            cursor: "move",
            helper: fixHelperModified,
            stop: function(event, ui) {
                series_order_changed(chart_id, chart_data);
            },
            tolerance: "pointer",

        }).disableSelection();
    }

    series_order_changed = function(chart_id, chart_data) {
        ordered_filter_ids = [];
        $("#legend_container_" + chart_id + " table:first-child tbody tr").each(function() {
            ordered_filter_ids.push($(this).find("input").val());
        });

        update_plot(chart_id, chart_data, ordered_filter_ids);
    }

    setup_print_menu = function(chart_id) {
        $("#print_menu_" + chart_id).menu({menus: "div"});
        $("#print_menu_" + chart_id).hide();
        $("#print_menu_" + chart_id).mouseleave(function() {
            $("#print_menu_" + chart_id).hide();
        });
    }

    toggle_print_menu = function(e, chart_id) {
        $("#print_menu_" + chart_id).toggle();
        $("#print_menu_" + chart_id).offset({left: e.pageX, top: e.pageY});
    }

    update_events = function(chart_id) {
        // Bind plotclick event.
        $("#inner_container_"+chart_id).bind(
            "plotclick",
            function (event, pos, item) {
                if (item) {
                    url = window.location.protocol + "//" +
                        window.location.host +
                        item.series.meta[item.datapoint[0]]["link"];
                    window.open(url, "_blank");
                }
            });

        $("#inner_container_"+chart_id).bind(
            "plothover",
            function (event, pos, item) {
                $("#tooltip").remove();
                if (item) {
                    tooltip = item.series.meta[item.datapoint[0]]["tooltip"];
                    showTooltip(item.pageX, item.pageY, tooltip,
                                item.series.meta[item.datapoint[0]]["pass"]);
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
                '<a id="chart_menu_' + chart_id + '"' +
                ' onclick="toggle_print_menu(event, ' + chart_id + ')">' +
                '<img src="' + image_url + 'icon-print.png"></a>' +
                '</span>');

        $("#filter_links_container_" + chart_id).append(
            '<div class="print-menu" id="print_menu_' + chart_id + '">' +
                '<div class="print-menu-item"><a href="#" id="chart_csv_' +
                chart_id + '">' +
                'Download as CSV</a></div>' +
                '<div class="print-menu-item"><a target="_blank" href="#"' +
                ' id="chart_img_' + chart_id +
                '">View as image</a></div>' +
                '</div>');

        setup_print_menu(chart_id);
    }

    update_dates = function(chart_id, chart_data) {
        // Add dates(build number) fields and toggle legend checkbox.
        $("#dates_container_" + chart_id).append(
            '<span style="margin-left: 30px;">Start build number:&nbsp;&nbsp;</span>');
        $("#dates_container_" + chart_id).append(
            '<span><select id="start_date_' + chart_id + '"></select></span>');
        $("#dates_container_" + chart_id).append(
            '<span>&nbsp;&nbsp;&nbsp;&nbsp;End build number:&nbsp;&nbsp;</span>');
        $("#dates_container_" + chart_id).append(
            '<span><select id="end_date_' + chart_id + '"></select></span>');

        $("#dates_container_" + chart_id).append(
            '<span>&nbsp;&nbsp;&nbsp;&nbsp;<label for="is_legend_visible_' +
                chart_id + '">Toggle legend:</label>&nbsp;&nbsp;</span>');
        $("#dates_container_" + chart_id).append(
            '<span><input type="checkbox" id="is_legend_visible_' + chart_id + '" checked="checked"/></span>');
        $("#dates_container_" + chart_id).append(
            '<span style="float: right;"><input id="has_subscription_' +
                chart_id + '" type="hidden"/><a id="has_subscription_link_' +
                chart_id + '" href="javascript:void(0)"></a></span>');

        set_dates(chart_id, chart_data);
        apply_settings(chart_id, chart_data);
        add_settings_events(chart_id, chart_data);
    }

    set_dates = function(chart_id, chart_data) {
        // Populate date dropdowns.
        dates = [];
        for (iter in chart_data.test_data) {
	    item = chart_data.test_data[iter]["number"].split('.')[0];
            if (dates.indexOf(item) == -1) {
                dates.push(item);
            }
        }

        if (chart_data.has_build_numbers) {
            dates.sort(function(x,y) {return x-y;});
        } else {
            dates.sort();
        }

        for (i in dates) {
            $("#start_date_"+chart_id).append($("<option/>", {
                value: dates[i],
                text: dates[i]
            }));
            $("#end_date_"+chart_id).append($("<option/>", {
                value: dates[i],
                text: dates[i]
            }));
        }
        $("#end_date_"+chart_id+" option:last").attr("selected", "selected");
    }

    add_settings_events = function(chart_id, chart_data) {

        $("#start_date_"+chart_id).change(function() {
            update_plot(chart_id, chart_data, null);
            update_settings(chart_id, chart_data["report_name"]);
        });

        $("#end_date_"+chart_id).change(function() {
            update_plot(chart_id, chart_data, null);
        });

        $("#is_legend_visible_"+chart_id).change(function() {
            update_plot(chart_id, chart_data, null);
            update_settings(chart_id, chart_data["report_name"]);
        });

        $("#has_subscription_link_"+chart_id).click(function() {
            $("#has_subscription_" + chart_id).val(
                $("#has_subscription_" + chart_id).val() != "true");
            update_settings(chart_id, chart_data["report_name"]);
        });
    }

    apply_settings = function(chart_id, chart_data) {

        if (chart_data.user) { // Is authenticated.
            if (chart_data.user.start_date) {
                $("#start_date_" + chart_id).val(chart_data.user.start_date);
            }
            if (chart_data.user.is_legend_visible == false) {
                $("#is_legend_visible_" + chart_id).attr("checked", false);
            }

            set_subscription_link(chart_id, chart_data.user.has_subscription);
        }
    }

    update_settings = function(chart_id, report_name) {

        url = "/dashboard/image-charts/" + report_name + "/" +
            chart_id + "/+settings-update";

        $.ajax({
            url: url,
            type: "POST",
            data: {
                csrfmiddlewaretoken: csrf_token,
                start_date: $("#start_date_"+chart_id).val(),
                is_legend_visible: $("#is_legend_visible_"+chart_id).attr(
                    "checked"),
                has_subscription: $("#has_subscription_" + chart_id).val(),
            },
            success: function (data) {
                set_subscription_link(chart_id,
                                      data[0].fields.has_subscription);
            },
        });
    }

    set_subscription_link = function(chart_id, subscribed) {
        if (subscribed) {
            $("#has_subscription_"+chart_id).val(true);
            $("#has_subscription_link_"+chart_id).html(
                "Unsubscribe from target goal");
        } else {
            $("#has_subscription_"+chart_id).val(false);
            $("#has_subscription_link_"+chart_id).html(
                "Subscribe to target goal");
        }
    }

    update_urls = function(chart_id, report_name) {
        canvas = $("#inner_container_" + chart_id + " > .flot-base").get(0);
        var dataURL = canvas.toDataURL();
        document.getElementById("chart_img_" + chart_id).href = dataURL;
        export_url = "/dashboard/image-charts/" + report_name + "/" +
            chart_id + "/+export";
        document.getElementById("chart_csv_" + chart_id).href = export_url;
    }

    test_build_number = function(build_number, chart_id, has_build_numbers) {
        // Test if the build number/date is between specified
        // number/date boundaries.
        start_number = $("#start_date_" + chart_id).val();
        end_number = $("#end_date_" + chart_id).val();
        if (has_build_numbers) {
            build_number = parseInt(build_number);
            start_number = parseInt(start_number);
            end_number = parseInt(end_number);
        }
        if (build_number <= end_number && build_number >= start_number) {
	    return true;
        }
        return false;
    }


    update_plot = function(chart_id, chart_data, ordered_filter_ids) {

        // Init plot data.
        plot_data = {};

        for (iter in chart_data.test_data) {

	    row = chart_data.test_data[iter];
	    test_filter_id = row["test_filter_id"];
            if (!(test_filter_id in plot_data)) {
                plot_data[test_filter_id] = {
                    "alias": row["alias"],
                    "representation": row["filter_rep"],
                    "data": [],
                    "meta": []
                };
            }
        }

        // Maximum number of test runs.
        max_iter = 0;
        // Store all build numbers
        build_numbers = [];

        for (iter in chart_data.test_data) {

	    row = chart_data.test_data[iter];
            build_number = row["number"].split(".")[0];

            // If some of the filters have build_number_attribute, ignore
            // others which don't.
            if (chart_data.has_build_numbers && !isNumeric(build_number)) {
                continue;
            }

            test_filter_id = row["test_filter_id"];
            if (test_build_number(build_number, chart_id,
                                  chart_data.has_build_numbers)) {

                // Current iterator for plot_data[iter][data].
                iter = plot_data[test_filter_id]["data"].length;

                if (chart_data["chart_type"] == "pass/fail") {
                    value = row["passes"];
                    tooltip = "Pass: " + value + ", Total: " + row["total"];

                } else {
                    value = row["measurement"];
                    tooltip = "Value: " + value;
                }

                meta_item = {
                    "link": row["link"],
                    "pass": row["pass"],
                    "tooltip": tooltip,
                };
                if (chart_data.has_build_numbers) {
                    insert_data_item([build_number, value],
                                     plot_data[test_filter_id]["data"]);
                    plot_data[test_filter_id]["meta"][build_number] = meta_item;
                    build_numbers.push(build_number);

                } else {
                    plot_data[test_filter_id]["data"].push([iter, value]);
                    plot_data[test_filter_id]["meta"][iter] = meta_item;
                }

                if (iter > max_iter) {
                    max_iter = iter;
                }
            }
        }

        data = [];

        // Prepare data and additional drawing options in series.
        bar_alignement = ["left", "center", "right"];
        alignement_counter = 0;

        if (!ordered_filter_ids) {
            ordered_filter_ids = Object.keys(plot_data);
        }
        for (var i in ordered_filter_ids) {
            test_filter_id = ordered_filter_ids[i];
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

            data.push({
                label: plot_data[test_filter_id]["alias"],
                data: plot_data[test_filter_id]["data"],
                meta: plot_data[test_filter_id]["meta"],
                bars: bars_options,
                lines: lines_options,
                test_filter_id: test_filter_id,
            });
        }

        // Get all build numbers to be used as tick labels.
        build_numbers = [];
        for (iter in chart_data.test_data) {

	    row = chart_data.test_data[iter];

	    build_number = row["number"].split('.')[0];

            if (test_build_number(build_number, chart_id,
                                  chart_data.has_build_numbers)) {

	        if (!isNumeric(build_number)) {
	            build_number = format_date(build_number);
	        }
                if (build_numbers.indexOf(build_number) == -1) {
	            build_numbers.push(build_number);
                }
            }
        }

        // Add target goal dashed line to the plot.
        if (chart_data["target_goal"]) {
	    goal_data = [];

            if (chart_data.has_build_numbers) {
	        for (var i in build_numbers) {
	            goal_data.push([build_numbers[i],
                                    chart_data["target_goal"]]);
	        }
            } else {
	        for (iter = 0; iter <= max_iter; iter++) {
	            goal_data.push([iter, chart_data["target_goal"]]);
	        }
            }

	    data.push({
                data: goal_data, dashes: {show: true},
                lines: {show: false}, color: "#999999"
            });
        }

        chart_width = $("#inner_container_" + chart_id).width();

        show_legend = true;
        if ($("#is_legend_visible_" + chart_id).attr("checked") == false) {
            $("#legend_container_" + chart_id).html("");
            $("#legend_container_" + chart_id).css("width", "0");
            $("#inner_container_" + chart_id).css("width", "98%");
            $("#dates_container_" + chart_id).css("width", "95%");
            $("#filter_links_container_" + chart_id).css("width", "95%");
            show_legend = false;
        } else {
            $("#legend_container_" + chart_id).css("width", "15%");
            $("#inner_container_" + chart_id).css("width", "82%");
            $("#dates_container_" + chart_id).css("width", "80%");
            $("#filter_links_container_" + chart_id).css("width", "80%");
        }

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
	        show: show_legend,
	        position: "nw",
                //            margin: [chart_width-40, 0],
	        container: "#legend_container_" + chart_id,
	        labelFormatter: function(label, series) {
                    label_hidden = "<input type='hidden' value='" +
                        series.test_filter_id + "'/>";
		    return label + label_hidden;
	        },
	    },
	    xaxis: {
	        tickDecimals: 0,
	        tickFormatter: function (val, axis) {
                    if (chart_data.has_build_numbers) {
                        return val;
                    } else {
		        return build_numbers[val];
                    }
	        },
	    },
	    yaxis: {
	        tickDecimals: 0,
                labelWidth: 25,
	    },
            canvas: true,
        };

        $.plot($("#outer_container_" + chart_id + " #inner_container_" + chart_id), data, options);

        // Setup sortable legend.
        setup_sortable(chart_id, chart_data);
    }

    isNumeric = function(n) {
        return !isNaN(parseFloat(n)) && isFinite(n);
    }

    insert_data_item = function(item, data) {
        // Insert item at the sorted position in the data.
        // data represents list of two-value lists.
        if (data.length == 0 || parseInt(item[0]) <= parseInt(data[0][0])) {
            data.splice(0, 0, item);
            return;
        }
        for (var i=0; i < data.length-1; i++) {
            if (parseInt(item[0]) > parseInt(data[i][0]) &&
                parseInt(item[0]) <= parseInt(data[i+1][0])) {
                data.splice(i+1, 0, item);
                return;
            }
        }
        data.splice(data.length, 0, item);
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


    // Add charts.
    for (chart_id in chart_data) {
        add_chart(chart_id, chart_data[chart_id]);
    }

});
