/* Dashboard plugin for jQuery */
(function($) {
  var _server = null;
  var _url = null;
  var _plot = {
    options: {},
    placeholder: null,
    data: []
  }

  var methods = {
    init: function(url, callback) {
      if (_server == null) {
        _url = url;
        _server = $.rpc(url, "xml", callback, "2.0");
      }
      return _server;
    },

    query_data_view: function(data_view_name, data_view_arguments, callback) {
      _server.query_data_view(callback, data_view_name, data_view_arguments);
    },

    graph: function(options) {
      _plot.options = options;
      _plot.placeholder = this;
      $.plot(_plot.placeholder, _plot.data, _plot.options);
    },

    query_series: function(query) {
      $().dashboard("query_data_view", query.name, query.args, function(response) {
        _plot.data.push({
          data: response.result.rows,
          label: query.label
        });
        $.plot(_plot.placeholder, _plot.data, _plot.options);
      });
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
            /* This is a bit hacky but will work for now */
            cell_link = _url + ".." + "/test-runs/" + cell + "/";
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
