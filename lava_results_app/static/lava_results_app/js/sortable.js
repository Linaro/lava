$.fn.sortable = function(){
    function disableSelection(sel){
	sel.preventDefault();
    }
    $(this).mousedown(function(e){
	var drag = $(this);
	var posParentTop = drag.parent().offset().top;
	var posParentBottom = posParentTop + drag.parent().height();
	var posOld = drag.offset().top;
	var posOldCorrection = e.pageY - posOld;
        drag.css({'z-index':2, 'background-color':'#eeeeee'});
	var mouseMove = function(e){
	    var posNew = e.pageY - posOldCorrection;
	    if (posNew < posParentTop){
		drag.offset({'top': posParentTop});
		if (drag.prev().length > 0 ) {
		    drag.insertBefore(drag.prev().css({'top':-drag.height()}).animate({'top':0}, 100));
		}
	    } else if (posNew + drag.height() > posParentBottom){
		drag.offset({'top': posParentBottom - drag.height()});
		if (drag.next().length > 0 ) {
		    drag.insertAfter(drag.next().css({'top':drag.height()}).animate({'top':0}, 100));
                }
	    } else {
		drag.offset({'top': posNew});
		if (posOld - posNew > drag.height() - 1){
		    drag.insertBefore(drag.prev().css({'top':-drag.height()}).animate({'top':0}, 100));
		    drag.css({'top':0});
		    posOld = drag.offset().top;
		    posNew = e.pageY - posOldCorrection;
		    posOldCorrection = e.pageY - posOld;
		} else if (posNew - posOld > drag.height() - 1){
		    drag.insertAfter(drag.next().css({'top':drag.height()}).animate({'top':0}, 100));
		    drag.css({'top':0});
		    posOld = drag.offset().top;
		    posNew = e.pageY - posOldCorrection;
		    posOldCorrection = e.pageY - posOld;
		}
	    }
	};
	var mouseUp = function(){
	    $(document).off('mousemove', mouseMove).off('mouseup', mouseUp);
	    $(document).off(($.support.selectstart?'selectstart':'mousedown')+'.ui-disableSelection', disableSelection);
            drag.animate({'top':0}, 100, function(){
		drag.css({'z-index':1, 'background-color':'transparent'});
	    });
        };
	$(document).on('mousemove', mouseMove).on('mouseup', mouseUp).on('contextmenu', mouseUp);
	$(document).on(($.support.selectstart?'selectstart':'mousedown')+'.ui-disableSelection', disableSelection);
        $(window).on('blur', mouseUp);
    });
}

$('.sort').sortable();
