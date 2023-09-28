let exper_template = `{{#value}}<tr>
<td> <a target="_blank" href="{{_id}}/info">{{ name }}</a> </td>
<td class="d-none exp_actions"></td>
<td> {{#FormatDate}}{{first_run.begin_time }}{{/FormatDate}} </td>
<td> {{#FormatDate}}{{last_run.begin_time}}{{/FormatDate}} </td>
<td> {{ contact_info }} </td>
<td> {{ description }} </td>
</tr>{{/value}}`;
let instrument_tab_template = `<li class="nav-item"><a class="nav-link instrument_tab" data-bs-toggle="tab" data-bs-target="#{{escaped_instr}}" role="tab" aria-controls="home-tab-pane" aria-selected="false">{{ instrument }}</a></li>`;
let instrument_tab_content_template = `<div role="tabpanel" class="tab-pane fade in" id="{{escaped_instr}}">
<div class="tabbable"><ul class="nav nav-pills" role="tablist"></ul></div>
<div class="tab-content"><div class="table-responsive">
<table class="table table-condensed table-striped table-bordered">
	<thead><tr><th>Name</th><th class="d-none exp_actions">Actions</th><th>First Run</th><th>Last Run</th><th>Contact</th><th>Description</th></tr></thead>
	<tbody></tbody>
</table>
</div></div>`;
let year_pill_template = `<li class="nav-item"><a class="nav-link year_pill" data-bs-toggle="tab" data-instrument="{{instrument}}" data-year="{{year}}" role="tab" aria-controls="home-tab-pane" aria-selected="false">{{ year }}</a></li>`;

Mustache.parse(exper_template);
Mustache.parse(instrument_tab_template);
Mustache.parse(instrument_tab_content_template);
Mustache.parse(year_pill_template);

let create_new_experiment = function() {
	async function loadAndShowRegistrationModal(modalurl) {
		console.log("Loading modal using '" + modalurl + "'. This resolves to '" + import.meta.resolve(modalurl) + "'");
		const { lgbk_create_edit_exp } = await import(modalurl);
		lgbk_create_edit_exp({ leader_account: logged_in_user, contact_info: _.get(logged_in_user_details, "gecos", logged_in_user) + "( " + logged_in_user + "@slac.stanford.edu )", start_time : moment(), end_time : moment().add(2, 'days')});
	}
	loadAndShowRegistrationModal("../static/html/mdls/exp/reg.js");
}

export function setupExperimentsPage() {
    document.addEventListener('DOMContentLoaded', () => { 
		WebSocketConnection.connect();
	
		var userdata = {}, experiments = {};
		$.when($.getJSON (useridgroups_url), $.getJSON ({ url: experiments_url }))
		.done(function( d1, d2 ) {
			userdata = d1[0].value, experiments = d2[0].value;
			console.log("Done getting experiments");
			if(_.get(privileges, "read", false)) {
				$("#activeexperimentsli").removeClass("d-none");$("#activeexptab").removeClass("d-none");
			}
			_.each(_.sortBy(_.keys(experiments)), function(instr) {
				var escaped_instr = instr.replace(/[ \/]/g, '_');
				$("#searchli").before(Mustache.render(instrument_tab_template, { instrument: instr, escaped_instr: escaped_instr }));
				$("#searchtab").before(Mustache.render(instrument_tab_content_template, { instrument: instr, escaped_instr: escaped_instr }))
			});
	
			if(_.get(privileges, "experiment_create", false)) {
				$("#user_create_exp").parent().removeClass("d-none");
				$("#user_create_exp").on("click", create_new_experiment);
			}
	
			$(".instrument_tab").on("shown.bs.tab", function(e){
				var instr = $(e.target).text();
				var tabtarget = $(e.target).attr("data-bs-target");
				console.log("Showing experiments for instrument " + instr + " in tab " + tabtarget);
			if ($(tabtarget + " .tabbable ul").find(".year_pill").length > 0) { $(tabtarget + " .tabbable ul").empty(); }
				if ($(tabtarget + " .tabbable ul").find(".year_pill").length <= 0) {
					console.log("Adding year pills for " + instr);
					_.each(_.reverse(_.sortBy(_.keys(experiments[instr]), function(x){ return _.includes([ "null" ], x) ? 0 : (isNaN(parseInt(x)) ? x : _.toNumber(x))})), function(year) {
						$(tabtarget + " .tabbable ul").append(Mustache.render(year_pill_template, { instrument: instr, year: (year == "null") ? "None" : year }));
					});
					$(tabtarget + " .tabbable ul").find(".year_pill").on("shown.bs.tab", function() {
						var instr = $(this).attr("data-instrument");
						var year = $(this).attr("data-year");
						console.log("Show experiments for " + instr + " for year " + year);
						var yrdt = experiments[instr][(year == "None") ? "null" : year]
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
				_.forOwn(experiments, function(value, instr) {
					if (instr != "OPS") {
						_.forOwn(experiments[instr], function(value, year) {
							_.forEach(experiments[instr][year], function(exp, index) {
								if ((exp['leader_account'] == userdata.userid) || (_.includes(userdata.groups, exp['posix_group'])) || _.includes(exp['players'], 'uid:'+userdata.userid )) {
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
			$("#activeexperimentsli a").on("shown.bs.tab", function(e){
				console.log("Showing active experiments");
				$.getJSON(active_experiments_url)
				.done(function(data){
					data.FormatDate = elog_formatdate;
					var rendered = Mustache.render(exper_template, data);
					$("#activeexptab tbody").html(rendered);
				});
			});
	
			if($("#activeexperimentsli").hasClass("d-none")) {
				$('#myexperimentsli a').tab('show');
			} else {
				$('#activeexperimentsli a').tab('show');
			}
	
			_.each(privileges, function(v, k){
				if(v) {
					$("#myNavbar").find(".priv_"+k).removeClass("d-none");
					$("#myexptab").find(".priv_"+k).removeClass("d-none");
				}
			})
	
			// Prepare for searches...
			var exp_names = []
			var name2info = {};
			_.forOwn(experiments, function(value, instr) {
				_.forOwn(experiments[instr], function(value, year) {
					_.forEach(experiments[instr][year], function(exp, index) {
						exp_names.push(exp['name']);
						name2info[exp['name']] = exp;
					})
				})
			});
	
			$("#searchtab").on("input", function(e) {
				if($("#searchtext").val().length > 1) {
					var curnamerx = new RegExp(".*"+$("#searchtext").val()+".*", 'i');
					var matchexps = _.filter(_.values(name2info), function(exp) {
						return curnamerx.test(exp["name"]) || curnamerx.test(exp["contact_info"]) || curnamerx.test(exp["description"]) || curnamerx.test(_.get(exp, "params.PNR"));
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
	
			document.querySelector("#experiments_container").addEventListener("experiments", function(event){
				let experiment = event.detail, experiment_name = experiment.value["name"];
				console.log("Processing experiment message for " + experiment_name);
				if(_.get(experiment, "CRUD", "") == "Create") {
					$.getJSON(experiment_name + "/ws/info")
					.done(function(d0){
						let exp = d0.value;
						if(_.isNil(_.get(experiments, [ exp["instrument"], null ], null))) { _.set(experiments, [ exp["instrument" ], null ], []) }
						let eidx = _.findIndex(_.get(experiments, [ exp["instrument"], null]), {"name": experiment_name});
						if (eidx >= 0) { _.get(experiments, [ exp["instrument"], null])[eidx] = exp; console.log("Replacing"); } else { _.get(experiments, [ exp["instrument"], null]).push(exp); }
						if($('#myexperimentsli a').hasClass("active")) { $('#myexperimentsli a').trigger("shown.bs.tab") }
					})
					.fail(function(){
						console.log("Experiment added for which we probably do not have permission " + experiment_name);
					})
				}
			});
		}).fail(function (errmsg) {
			error_message(errmsg);
		});
	
	})
}
