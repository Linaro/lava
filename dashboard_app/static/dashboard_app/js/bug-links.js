add_bug_link = function () {
    var current_bug = [];

    _submit = function () {

        if (!validate_submit()) {
            return;
        }

        var url = $("#add-bug-dialog").attr('url');
        // Increase or decrease bug number
        var increase = false;
        if (url.indexOf("unlink") == -1) {
            var increase = true;
        }

        bug_link = $("#add-bug-dialog").find('input[name=bug_link]').val();
        data = {
            csrfmiddlewaretoken: csrf_token,
            bug_link: bug_link,
            uuid: $("#add-bug-dialog").find('input[name=uuid]').val()
        }

        var relative_index = null;
        if($("#add_bug_dialog").find('input[name=relative_index]')) {
            relative_index = $("#add-bug-dialog").find('input[name=relative_index]').val();
            data["relative_index"] = relative_index;
        }

        $.ajax({
            url: url,
            async: false,
            type: "POST",
            data: data,
            beforeSend: function () {
                $('#loading_dialog').dialog('open');
            },
            success: function (data) {
                $('#loading_dialog').dialog('close');
                if (data[0].fields.analyzer_assigned_uuid) {
                    uuid = data[0].fields.analyzer_assigned_uuid;
                } else {
                    uuid = data[0].pk;
                }
                update_bug_dialog(uuid, increase, bug_link, relative_index);
                $("#add-bug-dialog").dialog('close');
            },
            error: function(data, status, error) {
                $('#loading_dialog').dialog('close');
                $("#add-bug-dialog").dialog('close');
                alert('Operation failed, please try again.');
            }
        });
    }

    update_bug_dialog = function (uuid, increase, bug_link, relative_index) {

        // Find corresponding td field and change number of bugs in it.
        if (relative_index) {
            element = $("span[data-uuid='" + uuid + "'][data-relative_index='" + relative_index + "'] > .add-bug-link");
        } else {
            element = $("span[data-uuid='" + uuid + "'] > p > .add-bug-link");
        }

        bug_number = element.html().replace("[", "").replace("]", "");

        if (relative_index) {
            bug_links_element = $("span[data-uuid='" + uuid + "'][data-relative_index='" + relative_index + "'] > .bug-links");
        } else {
            bug_links_element = $("span[data-uuid='" + uuid + "'] > .bug-links");
        }


        if (increase) {
            bug_links_element.append(
                '<li class="bug-link">' + bug_link + '</li>'
            );
            bug_number ++;
        } else {
            bug_number --;
            bug_links_element.children().each(function() {
                if ($(this).html().indexOf(bug_link) != -1) {
                    $(this).remove();
                }
            });
        }
        element.html("[" + bug_number + "]");
    }

    var add_bug_dialog = $('#add-bug-dialog').dialog(
        {
            autoOpen: false,
            buttons: {'Cancel': function () {$(this).dialog('close');}, 'OK': _submit },
            modal: true,
            title: "Link bug to XXX"
        });

    validate_submit = function() {
        bug_url = $("#add-bug-dialog").find('input[name=bug_link]').val();
        if (!isValidUrl(bug_url)) {
            alert("'" + bug_url + "' is not a valid url!!");
            return false;
        }
        if (current_bug.indexOf(bug_url) > -1) {
            alert("'" + bug_url + "' is already linked!!");
            return false;
        }
        return true;
    }

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
                            $('#add-bug-dialog').attr('url', unlink_bug_url);
                            add_bug_dialog.find('input[name=bug_link]').val(bug);
                            _submit();
                        }
                    }
                );
            } else {
                linked_div.hide();
            }

            var title = "Link a bug to '" + record + "'";
            $('#add-bug-dialog').attr('url', link_bug_url);
            add_bug_dialog.dialog('option', 'title', title);
            add_bug_dialog.dialog('open');
        }
    );
}
