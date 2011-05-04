/* Dashboard plugin for jQuery */
(function($) {
  var _server = null;
  var _url = null;
  var methods = {
    init: function(url, callback) {
      if (_server == null) {
        _url = url;
        _server = $.rpc(url, "xml", callback, "2.0");
      }
      return _server;
    },

    render_table: function(dataset, options) {
      var html = "<table class='data'>";
      html += "<tr>";
      $.each(dataset.columns, function (index, column) {
        html += "<th>" + column.name + "</th>";
      });
      html += "</tr>";
      $.each(dataset.rows, function (index, row) {
        html += "<tr>";
        $.each(row, function (index, cell) {
          var column = dataset.columns[index];
          var cell_html = undefined;
          var cell_link = null;
          if (cell_html == undefined) {
            cell_html = cell;
          }
          if (column.name == "UUID") {
            cell_link = "/dashboard/test-runs/" + cell + "/";
          }
          html += "<td>";
          if (cell_link) {
            html += "<a href='" + cell_link + "'>"
            html += cell_html;
            html += "</a>";
          } else {
            html += cell_html;
          }
          html += "</td>";
        });
        html += "</tr>";
      });
      html += "</table>";
      this.html(html);
    },

    render_to_table: function(data_view_name, data_view_arguments, options) {
      var outer = this;
      _server.query_data_view(function (response) {
        if (response.result) {
          outer.dashboard("render_table", response.result, options);
        } else {
          outer.html("Error code:" + response.error.faultCode + ", message: " + response.error.faultString);
        }
      }, data_view_name, data_view_arguments);
    }

  };

  $.fn.dashboard = function(method) {
    if (methods[method]) {
      return methods[method].apply(this, Array.prototype.slice.call(arguments, 1));
    } else if (typeof method == "object" || !method) {
      return methods.init.apply(this, arguments);
    } else {
      $.error("Method " + method + "does not exist on jQuery.dashboard");
    }
  };
})(jQuery);
