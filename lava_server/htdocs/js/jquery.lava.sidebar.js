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
      // hidden by default (unless pinned)
      hidden: true, 
      // not pinned by default
      pinned: false,  
      pinnedCookieName: "lava-sidebar-pinned",
      pinnedCookiePath: "/",
      extraControls: [],
      onShow: null,
      onHide: null,
      onDestroy: null,
      onPin: null,
      onUnpin: null,
    },
    _pin_button: null,
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
        // Load cookie to check for pin status
        this._load_pin_option();
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
        // Initialize pin button
        self._pin_button = $("<span/>", {
            title: "Pin/unpin the sidebar"
          })
        .button({
            text: false,
            icons: { primary: this.options.pinned ? 'ui-icon-pin-s' : 'ui-icon-pin-w'}
          })
          .click(function(event) {
            self.element.sidebar("option", "pinned", !self.options.pinned);
          })
          .appendTo(self._controls);
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
      if (this.options.pinned == false && this.options.hidden == true) {
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
    pin: function() {
      /* Pin the sidebar so that it is shown by default */
      this._set_pinned(true);
    },
    unpin: function() {
      /* Unpin the sidebar */
      this._set_pinned(false);
    },
    _set_pinned: function(pin_state) {
      this.options.pinned = (pin_state == true);
      this._pin_button.button("option", "icons", { primary: this.options.pinned ? 'ui-icon-pin-s' : 'ui-icon-pin-w'});
      this._save_pin_option();
      if (this.options.pinned == true && this.options.onPin) {
        this.options.onPin();
      }
      if (this.options.pinned == false && this.options.onUnpin) {
        this.options.onUnpin();
      }
    },
    _load_pin_option: function() {
      this.options.pinned = $.cookie(
        this.options.pinnedCookieName, {
          path: this.optionsPinnedCookiePath,
          expires: 365
        }) == "pinned";
    },
    _save_pin_option: function() {
      $.cookie(
        this.options.pinnedCookieName,
        this.options.pinned ? "pinned" : "", {
          path: this.options.pinnedCookiePath,
          expires: 365
        });
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
      if (key == "pinned") {
        this._set_pinned(value);
      }
    }
  });
})(jQuery);
