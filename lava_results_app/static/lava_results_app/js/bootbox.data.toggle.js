/**
 * Add shared method which allows special data-toggle value 'confirm' which
 * creates the bootbox confirm dialog when used.
 */
add_bootbox_data_toggle = function() {
    $(document).on("click", "[data-toggle=\"confirm\"]", function(e) {
        e.preventDefault();
        href = $(this).attr('href');
        bootbox.confirm($(this).attr("data-title"), function(result) {
            if(result) {
                top.location.href = href;
            }
        });
    });
}
