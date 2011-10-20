/**
* LAVA Sidebar plugin for jQuery
* http://launchpad.net/lava-server/
* Copyright (c): 2011 Zygmunt Krynicki
* Licensed under AGPLv3.
**/
(function($) {
  var baseClass = "lava-sidebar";
  var hiddenClass = "lava-sidebar-hidden";

  $.widget("lava.sidebar", {
    options: {
      hidden: false, 
      extraControls: [],
      onShow: null,
      onHide: null,
      onDestroy: null,
    },
    _close_button: null,
    _controls: null,
    controls: function() {
      /* Container of sidebar controls */
      return this._controls;
    },
    _create: function() {
      /* Constructor */
      var self = this;
      if (this.element.html().trim() == "") {
        // If the sidebar was empty then just hide it
        this.element.hide();
      } else {
        // Initialize basic stuff:
        // 1) css class
        // 2) click handler
        this.element
          .addClass(baseClass)
          .bind("click.sidebar", function(event) {
            if (self.element.hasClass(hiddenClass)) {
              self.show();
              event.preventDefault();
              event.stopPropagation();
            }
          });
        // Initialize controls bar
        self._controls = $("<div/>", {
            "class": "lava-sidebar-controls"
          })
          .prependTo(this.element);
        // Initialize close button
        self._close_button = $("<span/>", {
            title: "Collapse the sidebar"
          })
          .button({
            text: false,
            icons: { primary: 'ui-icon-circle-triangle-e'}
          })
          .bind("click", function(event) {
            self.hide(); 
            event.preventDefault();
            event.stopPropagation();
          })
          .appendTo(self._controls);
        $.each(self.options.extraControls, function(index, control) {
          control.appendTo(self._controls);
        });
      }
    },
    _init: function() {
      /* Initializer */
      if (this.options.hidden == true) {
        this.hide();
      } else {
        this.show();
      }
    },
    destroy: function() {
      /* Destructor */
      this.element.removeClass(baseClass);
      this.element.removeClass(hiddenClass);
      this.element.unbind("click.sidebar");
      this._controls.remove();
      $.Widget.prototype.destroy.call(this);
      if (this.options.onDestroy) {
        this.options.onDestroy();
      }
    },
    show: function() {
      /* Show the sidebar */
      this.element.removeClass(hiddenClass);
      this.options.hidden = false;
      if (this.options.onShow) {
        this.options.onShow();
      }
    },
    hide: function() {
      /* Hide the sidebar */
      this.element.addClass(hiddenClass);
      this.options.hidden = true;
      if (this.options.onHide) {
        this.options.onHide();
      }
    },
    _setOption: function(key, value) {
      /* jQueryUI widget method for implementing option setter */
      $.Widget.prototype._setOption.apply(this, arguments);
      if (key == "hidden") {
        if (value) {
          this.hide();
        } else {
          this.show();
        }
      }
    }
  });
})(jQuery);
