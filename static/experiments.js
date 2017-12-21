$(function() {
    $(document).ready(function() {
    	// This is an underscore template.
    	var exper_template = `{{#value}}<tr>
    		    <td> {{ experiment_id }} </td>
    		    <td> {{ experiment_name }} </td>
    		</tr>{{/value}}`;


    	Mustache.parse(exper_template); 
    	
        response = $.getJSON (experiments_for_instrument_url, {})
        .done(function( data ) {
        	console.log("Done getting data");
        	var rendered = Mustache.render(exper_template, data);
        	$("#experiments").html(rendered);
        })
        .fail(function (errmsg) {
        	noty( { text: errmsg, layout: "topRight", type: "error" } );
        });
    });
});
