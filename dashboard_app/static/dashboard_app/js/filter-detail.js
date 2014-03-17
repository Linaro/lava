var compareState = 0;
var compare1 = null, compare2 = null;
function cancelCompare () {
    $("#filter-detail-table").removeClass("select-compare1");
    $("#filter-detail-table").removeClass("select-compare2");
    $("#filter-detail-table").removeClass("select-compare3");
    $("#filter-detail-table tr").removeClass("selected-1");
    $("#filter-detail-table tr").removeClass("selected-2");
    $("#filter-detail-table tr").unbind("click");
    $("#filter-detail-table tr").unbind("hover");
    $("#filter-detail-table tr").each(removeCheckbox);
    $("#first-prompt").hide();
    $("#second-prompt").hide();
    $("#third-prompt").hide();
    $("#compare-button").button({label:"Compare builds"});
    compareState = 0;
}
function startCompare () {
    $("#compare-button").button({label:"Cancel"});
    $("#filter-detail-table").addClass("select-compare1");
    $("#filter-detail-table tr").click(rowClickHandler);
    $("#filter-detail-table tr").each(insertCheckbox);
    $("#filter-detail-table tr").hover(rowHoverHandlerIn, rowHoverHandlerOut);
    $("#first-prompt").show();
    compareState = 1;
}
function tagFromRow(tr) {
    var firstCell = $(tr).find("td:eq(0)");
    return {
        machinetag: firstCell.find("span").data("machinetag"),
        usertag: firstCell.text()
    };
}
function rowClickHandler() {
    if (compareState == 1) {
        compare1 = tagFromRow($(this));
        $(this).addClass("selected-1");
        $(this).find("input").attr("checked", true);
        $("#p2-build").text(compare1.usertag);
        $("#first-prompt").hide();
        $("#second-prompt").show();
        $("#filter-detail-table").removeClass("select-compare1");
        $("#filter-detail-table").addClass("select-compare2");
        compareState = 2;
    } else if (compareState == 2) {
        var thistag = tagFromRow($(this));
        if (compare1.machinetag == thistag.machinetag) {
            cancelCompare();
            startCompare();
        } else {
            compare2 = thistag;
            $(this).find("input").attr("checked", true);
            $(this).addClass("selected-2");
            $("#second-prompt").hide();
            $("#third-prompt").show();
            $("#filter-detail-table").removeClass("select-compare2");
            $("#filter-detail-table").addClass("select-compare3");
            $("#filter-detail-table input").attr("disabled", true);
            $("#filter-detail-table .selected-1 input").attr("disabled", false);
            $("#filter-detail-table .selected-2 input").attr("disabled", false);
            $("#p3-build-1").text(compare1.usertag);
            $("#p3-build-2").text(compare2.usertag);
            $("#third-prompt a").attr("href", window.location.pathname + '/+compare/' + compare1.machinetag + '/' + compare2.machinetag);
            compareState = 3;
        }
    } else if (compareState == 3) {
        var thistag = tagFromRow($(this));
        if (thistag.machinetag == compare1.machinetag || thistag.machinetag == compare2.machinetag) {
            $("#second-prompt").show();
            $("#third-prompt").hide();
            $("#filter-detail-table").addClass("select-compare2");
            $("#filter-detail-table").removeClass("select-compare3");
            $("#filter-detail-table input").attr("disabled", false);
            compareState = 2;
            $(this).find("input").attr("checked", false);
            if (thistag.machinetag == compare1.machinetag) {
                compare1 = compare2;
                $("#filter-detail-table .selected-1").removeClass("selected-1");
                $("#filter-detail-table .selected-2").addClass("selected-1");
                $("#p2-build").text(compare1.usertag);
            }
            $("#filter-detail-table .selected-2").removeClass("selected-2");
        }
    }
    tagFromRow(this);
}
function rowHoverHandlerIn() {
    $(this).addClass("hover");
}
function rowHoverHandlerOut() {
    $(this).removeClass("hover");
}
function insertCheckbox() {
    var row = $(this);
    var checkbox = $('<input type="checkbox">');
    row.find("td:first").prepend(checkbox);
}
function removeCheckbox() {
    var row = $(this);
    row.find('input').remove();
}
$(window).load(
    function () {
        $("#filter-detail-table").dataTable().fnSettings().fnRowCallback = function(tr, data, index) {
            if (compareState) {
                insertCheckbox.call(tr);
                $(tr).click(rowClickHandler);
                $("#filter-detail-table tr").hover(rowHoverHandlerIn, rowHoverHandlerOut);
                if (compareState >= 2 && tagFromRow(tr).machinetag == compare1.machinetag) {
                    $(tr).addClass("selected-1");
                    $(tr).find("input").attr("checked", true);
                }
                if (compareState >= 3) {
                    if (tagFromRow(tr).machinetag == compare2.machinetag) {
                        $(tr).addClass("selected-2");
                        $(tr).find("input").attr("checked", true);
                    } else if (tagFromRow(tr).machinetag != compare1.machinetag) {
                        $(tr).find("input").attr("disabled", true);
                    }
                }
            }
            return tr;
        };
        $("#compare-button").button();
        $("#compare-button").click(
            function (e) {
                if (compareState == 0) {
                    startCompare();
                } else {
                    cancelCompare();
                }
            }
        );
        $("div.dataTables_length").remove();
        $("div.dataTables_info").remove();
    }

);
