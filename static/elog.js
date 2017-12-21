$(function() {
    $(document).ready(function() {
    	// This is an mustache template.
    	var elog_template = `{{#value}}<tr>
    		    <td> {{ insert_time }} </td>
    		    <td> {{ run_num }} </td>
    		    <td> {{ content }} </td>
    		    <td> {{ author }} </td>
    		</tr>{{/value}}`;


    	Mustache.parse(elog_template); 
    	
        response = $.getJSON (elog_for_experiment_url, {})
        .done(function( data ) {
        	console.log("Done getting data");
        	var rendered = Mustache.render(elog_template, data);
        	$("#elogs").html(rendered);
            WebSocketConnection.connect();
            $(document).on('elog', function(event, elogData) {
            	console.log("Processing elog event for experiment " + experiment_name);
            	if ('CRUD' in elogData && elogData['CRUD'] == 'INSERT') {
                	var single_elog_item =  Mustache.render(elog_template, elogData);
                	$("#elogs").prepend(single_elog_item);
            	}   
            });
        })
        .fail(function (errmsg) {
        	noty( { text: errmsg, layout: "topRight", type: "error" } );
        });
    });
});
