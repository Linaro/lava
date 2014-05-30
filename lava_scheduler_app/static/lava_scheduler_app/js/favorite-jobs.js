$(document).ready(function () {

    $("#user_favorite_job").click(function() {
        $("#username").val("");
        $('#user_select_dialog').dialog('open');
    });

    $('#user_select_dialog').dialog({
        autoOpen: false,
        title: 'Select user',
        draggable: false,
        height: 120,
        width: 350,
        modal: true,
        resizable: false,
        dialogClass: 'user-select-dialog'
    });

    $("#username").autocomplete({
        source: "/scheduler/username-list-json",
        minLength: 1,
    });

    $("#submit").click(function() {
        window.location.href = "/scheduler/favorite-jobs/~" +
            $("#username").val();
    });

});
