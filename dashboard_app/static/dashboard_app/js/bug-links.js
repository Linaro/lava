add_bug_link = function () {
    var current_bug = [];

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

    isValidUrl = function(url) {
        return url.match(/^https?:\/\/[a-z0-9-\.]+\.[a-z]{2,4}\/?([^\s<>\#%"\,\{\}\\|\\\^\[\]`]+)?$/);
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

            var linked_div = add_bug_dialog.find('div.linked');
            var record = $(this).closest('span').data('record');
            var uuid = $(this).closest('span').data('uuid');
            var rel_idx = $(this).closest('span').data('relative_index');
            var relative_index = $(this).closest('span').data('relative_index');

            current_bug = get_linked_bugs($(this));
            add_bug_dialog.find('input[name=bug_link]').val('');
            add_bug_dialog.find('input[name=uuid]').val(uuid);

            if (rel_idx) {
                add_bug_dialog.find('input[name=relative_index]').val(rel_idx);
            }

            if(current_bug.length) {
                var html = "<b>Bug(s) linked to " + record + ":</b><table width='95%' border='0'>";
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

            var title = "Link a bug to '" + record + "'";
            $('#add-bug-dialog').attr('action', link_bug_url);
            add_bug_dialog.dialog('option', 'title', title);
            add_bug_dialog.dialog('open');
        }
    );
}
