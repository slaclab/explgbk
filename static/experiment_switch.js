$(function() {
	var instrument_template = `{{#value}}<tr">
	<td>{{ instrument }}</td>
	<td>{{ station }}</td>
	<td>{{ name }}</td>
	<td>{{ contact_info }}</td>
	<td>{{ description }}</td>
	<td>{{#FormatDate}}{{ switch_time }}{{/FormatDate}}</td>
	<td>{{ requestor_uid }}</td>
	<td><a class="btn btn-primary expswitch" role="button" data-instrument="{{ instrument }}" data-station="{{ station }}">Switch</a></td>
	</tr>{{/value}}`;

	var exper_template = `{{#value}}<tr data-expname="{{ name }}">
	    <td> <a target="_blank" href="{{_id}}/">{{ name }}</a> </td>
	    <td> {{ contact_info }} </td>
	    <td> {{ description }} </td>
	</tr>{{/value}}`;

	Mustache.parse(instrument_template);
	Mustache.parse(exper_template);

    $(document).ready(function() {
    	$("#switch_experiment").on("click", function(){
    		var exp_switch_info = $('#choose_experiment_modal table').data("selected-experiment");
    		console.log("Switching " + exp_switch_info.instrument + " station " + exp_switch_info.station + " to experiment " + exp_switch_info.experiment_name);
    		$("#choose_experiment_modal").modal("hide");
    		$.ajax({
    			type: "POST",
    			contentType: "application/json; charset=utf-8",
    			url: switch_experiment_url,
    			data: JSON.stringify(exp_switch_info),
    			dataType: "json"
    		})
    		.done(function(data, textStatus, jqXHR) {
    			if(data.success) {
        			console.log("Successfully switched " + exp_switch_info.instrument + " station " + exp_switch_info.station + " to experiment " + exp_switch_info.experiment_name);
        			location.reload();
    			} else {
    				alert("Server side exception switching experiment " + data.errormsg);
    			}
    		})
    		.fail( function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); alert("Server side exception switching experiment " + jqXHR.responseText); })
    	});
    	$.when($.getJSON(active_experiments_url), $.getJSON(instrument_station_list))
    	.done(function(d1, d2) {
				var active_exps = d1[0], ins_st_list = d2[0];
				var others = _.differenceWith(ins_st_list.value, active_exps.value, function(av, ov){ return av['instrument'] == ov['instrument'] && av['station'] == ov['station'] });
				_.each(others, function(ot){ active_exps.value.push(ot); });
    		active_exps.FormatDate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY");}};
    		var rendered = Mustache.render(instrument_template, active_exps);
    		$("#switch_experiment_div tbody").html(rendered);
    		$("a.expswitch").on("click", function() {
    			var instr = $(this).attr("data-instrument");
    			var station = $(this).attr("data-station");
    			console.log("Switch " + instr + "/" + station);
    			$("#choose_experiment_modal .modal-title").text("Choose new experiment for " + instr + "(" + station + ")");
    			$.getJSON(experiments_url)
    			.done(function(data) {
    				var experiments_for_instrument = data.value[instr];
    				var rendered = Mustache.render(exper_template, {value: experiments_for_instrument});
    				$("#choose_experiment_modal table tbody").html(rendered);
    				$('#choose_experiment_modal table').on('click', 'tbody tr', function(event) {
    					$(this).find("td").addClass('bg-info');
    					$(this).siblings().find("td").removeClass('bg-info');
    					$('#choose_experiment_modal table').data("selected-experiment", {instrument: instr, station: station, experiment_name: $(this).attr("data-expname")});
    				});
    				$("#choose_experiment_modal").modal("show");
    			}).fail(function() {
    				alert("There was an error fetching experiments from the server.");
    			});
    		})
    	});
    });
});
