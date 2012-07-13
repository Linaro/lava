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
// Hook up the event and run resize ASAP (looks jumpy in FF if you
// don't run it here).
$(window).ready(
    function () {
      $(window).resize(_resize);
      $("#scroller").scrollLeft(100000);
      _resize();
    });
// Because what resize does depends on the final sizes of elements,
// run it again after everything is loaded (things end up wrong in
// chromium if you don't do this).
$(window).load(_resize);
