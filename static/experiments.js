$(function() {
    $(document).ready(function() {
    	var exper_template = `{{#value}}<tr>
    		    <td> <a target="_blank" href="{{_id}}/">{{ name }}</a> </td>
                <td class="d-none exp_actions"></td>
    		    <td> {{#FormatDate}}{{first_run.begin_time }}{{/FormatDate}} </td>
    		    <td> {{#FormatDate}}{{last_run.begin_time}}{{/FormatDate}} </td>
    		    <td> {{ contact_info }} </td>
    		    <td> {{ description }} </td>
    		</tr>{{/value}}`;

    	var instrument_tab_template = `<li class="nav-item"><a class="nav-link instrument_tab" data-toggle="tab" href="#{{escaped_instr}}">{{ instrument }}</a></li>`;
    	var instrument_tab_content_template = `<div role="tabpanel" class="tab-pane fade in" id="{{escaped_instr}}"><div class="tabbable"><ul class="nav nav-pills"></ul></div><div class="tab-content"><div class="table-responsive">
            <table class="table table-condensed table-striped table-bordered">
            <thead><tr><th>Name</th><th class="d-none exp_actions">Actions</th><th>First Run</th><th>Last Run</th><th>Contact</th><th>Description</th></tr></thead>
            <tbody>
            </tbody>
          </table></div></div>`;
    	var year_pill_template = `<li class="nav-item"><a class="nav-link year_pill" data-toggle="tab" data-instrument="{{instrument}}" data-year="{{year}}" href="#{{year}}">{{ year }}</a></li>`;


    	Mustache.parse(exper_template);
    	Mustache.parse(instrument_tab_template);
    	Mustache.parse(instrument_tab_content_template);
    	Mustache.parse(year_pill_template);

    	$.when($.getJSON (useridgroups_url), $.getJSON ({ url: experiments_url }))
        .done(function( d1, d2 ) {
        	var userdata = d1[0], data = d2[0];
        	console.log("Done getting experiments");
            if(_.get(privileges, "read", false)) {
                $("#activeexperimentsli").removeClass("d-none");$("#activeexptab").removeClass("d-none");
            }
            _.each(_.sortBy(_.keys(data.value)).reverse(), function(instr) {
              var escaped_instr = instr.replace(/[ \/]/g, '_');
              $("#activeexperimentsli").after(Mustache.render(instrument_tab_template, { instrument: instr, escaped_instr: escaped_instr }));
              $("#activeexptab").after(Mustache.render(instrument_tab_content_template, { instrument: instr, escaped_instr: escaped_instr }))
            });

            if(_.get(privileges, "experiment_create", false)) {
                $("#user_create_exp").parent().removeClass("d-none");
                $("#user_create_exp").on("click", function(){
                    lgbk_create_edit_exp({ leader_account: logged_in_user, contact_info: _.get(logged_in_user_details, "gecos", logged_in_user) + "( " + logged_in_user + "@slac.stanford.edu )", start_time : moment(), end_time : moment().add(2, 'days')});
                })
            }

            // Bootstrap 4 bug; revist after each release...
            $('#myNavbar a[data-toggle="tab"]').on('click', function(e) {
                e.preventDefault();
                $(this).tab('show');
                var theThis = $(this);
                $('#myNavbar a').removeClass('active');
                theThis.addClass('active');
            });
        	$(".instrument_tab").on("shown.bs.tab", function(e){
        		var instr = $(e.target).text();
        		var tabtarget = $(e.target).attr("href");
        		console.log("Showing experiments for instrument " + instr + " in tab " + tabtarget);
        		if ($(tabtarget + " .tabbable ul").find(".year_pill").length <= 0) {
        			console.log("Adding year pills for " + instr);
        			_.each(_.reverse(_.sortBy(_.keys(data.value[instr]), function(x){ return _.includes([ "null" ], x) ? 0 : _.toNumber(x)})), function(year) {
	            		$(tabtarget + " .tabbable ul").append(Mustache.render(year_pill_template, { instrument: instr, year: (year == "null") ? "None" : year }));
	        		});
	        		$(tabtarget + " .tabbable ul").find(".year_pill").on("shown.bs.tab", function() {
	        			var instr = $(this).attr("data-instrument");
	        			var year = $(this).attr("data-year");
	        			console.log("Show experiments for " + instr + " for year " + year);
	        			var yrdt = data.value[instr][(year == "None") ? "null" : year]
	        			var expdata = {value: yrdt};
	        			expdata.FormatDate = elog_formatdate;
	        			var rendered = Mustache.render(exper_template, expdata);
	                	$(tabtarget + " table tbody").html(rendered);
	        		});
	        		$(tabtarget + " .tabbable .nav-pills a:first").tab('show');
        		}
        	});
        	$("#myexperimentsli a").on("shown.bs.tab", function(e){
        		console.log("Showing my experiments");
        		var myExps = [];
        		_.forOwn(data.value, function(value, instr) {
        			if (instr != "OPS") {
            			_.forOwn(data.value[instr], function(value, year) {
            				_.forEach(data.value[instr][year], function(exp, index) {
            					if ((exp['leader_account'] == userdata.value.userid) || (_.includes(userdata.value.groups, exp['posix_group'])) || _.includes(exp['players'], 'uid:'+userdata.value.userid )) {
            						myExps.push(exp);
            					}
            				});
            			});
        			}
        		});
                myExps = _.reverse(_.sortBy(myExps, ['end_time']));
    			var expdata = {value: myExps};
    			expdata.FormatDate = elog_formatdate;
    			var rendered = Mustache.render(exper_template, expdata);
        		$("#myexptab tbody").html(rendered);
        	});
        	$('#myexperimentsli a').tab('show');

        	$("#activeexperimentsli a").on("shown.bs.tab", function(e){
        		console.log("Showing active experiments");
        		$.getJSON(active_experiments_url)
        		.done(function(data){
        			data.FormatDate = elog_formatdate;
        			var rendered = Mustache.render(exper_template, data);
            		$("#activeexptab tbody").html(rendered);
        		});
        	});

            _.each(privileges, function(v, k){
                if(v) {
                    $("#myNavbar").find(".priv_"+k).removeClass("d-none");
                    $("#myexptab").find(".priv_"+k).removeClass("d-none");
                }
            })

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
        		if($("#searchtext").val().length > 1) {
                    var curnamerx = new RegExp(".*"+$("#searchtext").val()+".*", 'i');
                    var matchexps = _.filter(_.values(name2info), function(exp) {
                        return curnamerx.test(exp["name"]) || curnamerx.test(exp["contact_info"]) || curnamerx.test(exp["description"]);
                    });
        			if(matchexps.length > 0) {
        				var expdata = {value: matchexps};
            			expdata.FormatDate = elog_formatdate;
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
