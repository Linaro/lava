(function($){
    /* Fixes :focus in IE and any other browsers that don't support it */
    /* Copyright (C) James Padolsey http://james.padolsey.com */
    $.pseudoFocus = function() {
        
        var focusIsSupported = (function(){
            
            // Create an anchor + some styles including ':focus'.
            // Focus the anchor, test if style was applied,
            // if it was then we know ':focus' is supported.
            
            var ud = 't' + +new Date(),
                anchor = $('<a id="' + ud + '" href="#"/>').css({top:'-999px',position:'absolute'}).appendTo('body'),
                style = $('<style>#'+ud+'{font-size:10px;}#'+ud+':focus{font-size:1px !important;}</style>').appendTo('head'),
                supported = anchor.focus().css('fontSize') !== '10px';
            anchor.add(style).remove();
            return supported;
        
        })();
        
        if(focusIsSupported) { return; }
        
        var stylesToAdd = [],
            pseudoRegex = /:(unknown|focus)/,
            className = 'focus';
            
        $(document.styleSheets).each(function(i, sheet){
            var cssRules = sheet.cssRules || sheet.rules;
            $.each(cssRules, function(i, rule){
                $.each(rule.selectorText.split(','), function(i, selector){
                    var hasPseudoFocus = pseudoRegex.test(selector);
                    if (hasPseudoFocus) {
                        
                        var styles = rule.cssText ? rule.cssText.match(/\{(.+)\}/)[1] : rule.style.cssText,
                        
                            // Replace :focus with .focus (or whatever className):
                            newSelector = selector.replace(pseudoRegex,'.' + className);
                            
                        // Completell erase the pseudo-class, so we can select it.
                        selector = selector.replace(pseudoRegex,'');
                        
                        // Add style to stack:
                        stylesToAdd[stylesToAdd.length] = newSelector + '{' + styles + '}';
                        
                        // Add blur/focus handlers:
                        $(selector).each(function(){
                            
                            // If the selector targets a non-focusable element
                            // then we need the first parent that is focusable.
                            // [Warning: this could be abused]
                            var isAcceptable = 'a,input,textarea,button';
                            $($(this).is(isAcceptable) ? this : $(this).parents(isAcceptable)[0])
                                .bind('focus.pseudoFocus', function(){
                                    $(this).addClass(className);
                                })
                                .bind('blur.pseudoFocus', function(){
                                    $(this).removeClass(className);
                                });
                            
                            // Fix IE issue where element remains in focused
                            // state when returning to page (via back button):
                            if ($(this).is('a')) {
                                $(this).bind('click.pseudoFocus', function(){
                                    $(this).blur();
                                });
                            }
                            
                        });
                        
                    }
                });
            });
        });
        stylesToAdd && $('head').append('<style>' + stylesToAdd.join('') + '</style>');
        
    };
})(jQuery);