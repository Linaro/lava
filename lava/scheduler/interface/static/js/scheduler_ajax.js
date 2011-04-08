function get_test_cases(){
    new Ajax.Request('/scheduler/', { 
    method: 'post',
    parameters: $H({'test_suite':$('id_test_suite').getValue()}),
    onSuccess: function(transport) {
        var e = $('id_test_case')
        if(transport.responseText)
            e.update(transport.responseText)
    }
    }); // end new Ajax.Request
}
