$(function() {
    $(document).ready(function() {
    	var exper_template = `{{#value}}<tr>
    		    <td> <a target="_blank" href="{{_id}}/">{{ name }}</a> </td>
    		    <td> {{#FormatDate}}{{first_run.begin_time }}{{/FormatDate}} </td>
    		    <td> {{#FormatDate}}{{last_run.begin_time}}{{/FormatDate}} </td>
    		    <td> {{ contact_info }} </td>
    		    <td> {{ description }} </td>
    		</tr>{{/value}}`;

    	var instrument_tab_template = `<li><a class="instrument_tab" data-toggle="tab" href="#{{instrument}}">{{ instrument }}</a></li>`;
    	var instrument_tab_content_template = `<div role="tabpanel" class="tab-pane fade in" id="{{instrument}}"><div class="tabbable"><ul class="nav nav-pills"></ul></div><div class="tab-content"><div class="table-responsive">
            <table class="table table-condensed table-striped table-bordered">
            <thead><tr><th>Name</th><th>First Run</th><th>Last Run</th><th>Contact</th><th>Description</th></tr></thead>
            <tbody>
            </tbody>
          </table></div></div>`;
    	var year_pill_template = `<li><a class="year_pill" data-toggle="tab" data-instrument="{{instrument}}" data-year="{{year}}" href="#{{year}}">{{ year }}</a></li>`;
    	

    	Mustache.parse(exper_template);
    	Mustache.parse(instrument_tab_template);
    	Mustache.parse(instrument_tab_content_template);
    	Mustache.parse(year_pill_template);
    	
    	$.when($.getJSON (useridgroups_url), $.getJSON ({ url: experiments_url }))
        .done(function( d1, d2 ) {
        	var userdata = d1[0], data = d2[0];
        	console.log("Done getting experiments");
        	_.each(_.sortBy(_.keys(data.value)).reverse(), function(instr) { 
        		$("#activeexperimentsli").after(Mustache.render(instrument_tab_template, { instrument: instr }));
        		$("#activeexptab").after(Mustache.render(instrument_tab_content_template, { instrument: instr }))
        	});
        	$(".instrument_tab").on("shown.bs.tab", function(e){ 
        		var instr = $(e.target).text(); 
        		var tabtarget = $(e.target).attr("href");
        		console.log("Showing experiments for instrument " + instr + " in tab " + tabtarget);
        		if ($(tabtarget + " .tabbable ul").find(".year_pill").length <= 0) {
        			console.log("Adding year pills for " + instr);
        			_.each(_.keys(data.value[instr]).sort(function(a, b){ return b - a }), function(year) {
	            		$(tabtarget + " .tabbable ul").append(Mustache.render(year_pill_template, { instrument: instr, year: (year == "null") ? "None" : year }));
	        		});
	        		$(tabtarget + " .tabbable ul").find(".year_pill").on("shown.bs.tab", function() {
	        			var instr = $(this).attr("data-instrument");
	        			var year = $(this).attr("data-year");
	        			console.log("Show experiments for " + instr + " for year " + year);
	        			var yrdt = data.value[instr][(year == "None") ? "null" : year]
	        			var expdata = {value: yrdt};
	        			expdata.FormatDate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY");}};
	        			var rendered = Mustache.render(exper_template, expdata);
	                	$("#" + instr + " table tbody").html(rendered);
	        		});
	        		$(tabtarget + " .tabbable .nav-pills a:first").tab('show');
        		}
        	});
        	$("#myexperimentsli a").on("shown.bs.tab", function(e){
        		console.log("Showing my experiments");
        		var myExps = [];
        		_.forOwn(data.value, function(value, instr) {
        			if (instr != "NEH") {
            			_.forOwn(data.value[instr], function(value, year) {
            				_.forEach(data.value[instr][year], function(exp, index) {
            					if ((exp['leader_account'] == userdata.value.userid) || (_.includes(userdata.value.groups, exp['posix_group']))) {
            						myExps.push(exp);
            					} 
            				});
            			});
        			}
        		});
    			var expdata = {value: myExps};
    			expdata.FormatDate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY");}};
    			var rendered = Mustache.render(exper_template, expdata);
        		$("#myexptab tbody").html(rendered);
        	});
        	$('#myexperimentsli a').tab('show');
        	
        	$("#activeexperimentsli a").on("shown.bs.tab", function(e){
        		console.log("Showing active experiments");
        		$.getJSON(active_experiments_url)
        		.done(function(data){
        			data.FormatDate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY");}};
        			var rendered = Mustache.render(exper_template, data);
            		$("#activeexptab tbody").html(rendered);
        		});
        	});
        	
        	// Prepare for searches...
        	var exp_names = []
        	var name2info = {};
    		_.forOwn(data.value, function(value, instr) {
    			_.forOwn(data.value[instr], function(value, year) {
    				_.forEach(data.value[instr][year], function(exp, index) {
    					exp_names.push(exp['name']);
    					name2info[exp['name']] = exp;
    				})
    			})
    		});

        	
        	$("#searchtab").on("input", function(e) {
        		if($("#searchtext").val().length > 2) {
        			var curname = $("#searchtext").val();
        			var matchexps = [];
        			_.each(exp_names, function(exp_name){
        				if(_.startsWith(exp_name, curname)) {
        					matchexps.push(name2info[exp_name]);
        				}
        			});
        			if(matchexps.length > 0) {
        				var expdata = {value: matchexps};
            			expdata.FormatDate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY");}};
            			var rendered = Mustache.render(exper_template, expdata);
                		$("#searchresults tbody").html(rendered);
        			}
        		} else {
            		$("#searchresults tbody").empty();
        		}
        	});        	
        })
        .fail(function (errmsg) {
        	noty( { text: errmsg, layout: "topRight", type: "error" } );
        });
    });
});
