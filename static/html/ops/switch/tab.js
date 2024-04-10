import { show_switch_history, switch_experiment_on_station, put_instrument_in_standby } from "./actions.js";

var instrument_template = `{{#value}}<tr {{#is_standby}}class="exp_switch_standby"{{/is_standby}}">
<td style="background:{{background}}; color:{{color}}; " >{{ instrument }}</td>
<td>{{ station }}</td>
<td>{{#is_standby}}Standby{{/is_standby}}{{^is_standby}}<a target="_blank" href="../{{_id}}/info">{{ name }}</a>{{/is_standby}}</td>
<td>{{ contact_info }}</td>
<td>{{ leader_account }}</td>
<td>{{ current_sample }}</td>
<td {{#current_run}}{{^current_run.end_time}}class="expswitch_run_open" title="The run is still active as of {{#FormatDateTime}}{{ current_run.begin_time }}{{/FormatDateTime}}"{{/current_run.end_time}}{{#current_run.end_time}} title="The run was marked done at {{#FormatDateTime}}{{ current_run.end_time }}{{/FormatDateTime}}"{{/current_run.end_time}}>{{ current_run.num }}{{/current_run}}</td>
<td>{{ description }}</td>
<td>{{#FormatDateTime}}{{ switch_time }}{{/FormatDateTime}}</td>
<td>{{ requestor_uid }}</td>
<td class="ops_switch_icons">
  <span class="expswitch" data-instrument="{{ instrument }}" data-station="{{ station }}" title="Switch to a new experiment"><i class="fas fa-exchange-alt fa-lg" aria-hidden="true"></i></span>
  {{^is_standby}}<span class="standby"  data-instrument="{{ instrument }}" data-station="{{ station }}" title="Put this station in standby mode."><i class="fas fa-power-off fa-lg" aria-hidden="true"></i></span>{{/is_standby}}
  <span class="switch_history" data-instrument="{{ instrument }}" data-station="{{ station }}" title="Show the history of changes to this instrument station"><i class="fas fa-history fa-lg"></i></span>
</td>
</tr>{{/value}}`;

Mustache.parse(instrument_template);

export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="expswitch_tab">
	<div class="row" id="switch_experiment_div">
	  <div class="table-responsive">
		<table class="table table-condensed table-striped table-bordered">
		  <thead><tr><th>Instrument</th><th>Station</th><th>Experiment</th><th>PI</th><th>Leader Account</th><th>Current Sample</th><th>Current Run</th><th>Description</th><th>Switched at</th><th>Switched by</th><th><i class="fas fa-exchange-alt fa-lg" aria-hidden="true"></i></th></tr></thead>
		  <tbody></tbody>
		</table>
	  </div>
	</div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

	$.when($.getJSON(active_experiments_url), $.getJSON(instrument_station_list), $.getJSON({ url: "../ws/instruments" }))
	.done(function(d1, d2, d3) {
		var active_exps = d1[0], ins_st_list = d2[0], instruments = _.keyBy(d3[0].value, "_id");
		var others = _.differenceWith(ins_st_list.value, active_exps.value, function(av, ov){ return av['instrument'] == ov['instrument'] && av['station'] == ov['station'] });
		_.each(others, function(ot){ active_exps.value.push(ot); });
		_.each(active_exps.value, function(exp){ exp["background"] = _.get(instruments, exp["instrument"] + ".color", "inherit"); exp["color"] = _.has(instruments, exp["instrument"] + ".color") ? "white" : "black"; });
		active_exps.FormatDate = elog_formatdate;
		active_exps.FormatDateTime = elog_formatdatetime;
		var rendered = Mustache.render(instrument_template, active_exps);

		$("#switch_experiment_div tbody").html(rendered);

		$("span.expswitch").on("click", switch_experiment_on_station)
		$("span.standby").on("click", put_instrument_in_standby);
		$("span.switch_history").on("click", show_switch_history)
	});
}
