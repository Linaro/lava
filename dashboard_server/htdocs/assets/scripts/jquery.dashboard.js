/* Dashboard plugin for jQuery */
(function($) {
  var server = null;
  var methods = {
    init: function(callback) {
      server = $.rpc("/xml-rpc/", "xml", callback, "2.0");
      return server;
    },

    render_table: function(dataset) {
      var html = "<table class='data'>";
      html += "<tr>";
      $.each(dataset.columns, function (index, column) {
        html += "<th>" + column.name + "</th>";
      });
      html += "</tr>";
      $.each(dataset.rows, function (index, row) {
        html += "<tr>";
        $.each(row, function (index, cell) {
          html += "<td>" + cell + "</td>";
        });
        html += "</tr>";
      });
      html += "</table>";
      this.html(html);
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
