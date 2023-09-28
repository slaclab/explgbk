var exper_template = `{{#value}}<tr data-expname="{{ name }}">
	<td> <a target="_blank" href="../{{_id}}/info">{{ name }}</a> </td>
	<td> {{ contact_info }} </td>
	<td> {{ leader_account }} </td>
	<td> {{ description }} </td>
</tr>{{/value}}`;
Mustache.parse(exper_template);

export function show_switch_history() { 
    let instrument = $(this).attr("data-instrument"), station=$(this).attr("data-station");
    $.when($.ajax ("../../static/html/ops/switch/history.html"), $.getJSON("../ws/instrument_switch_history", {"instrument": instrument, "station": station}))
    .done(function( d0, d1 ) {
        let htmpl = d0[0], shistories = d1[0].value, ish = {"instrument": instrument, "station": station, "switches": shistories};
        Mustache.parse(htmpl);
        ish.FormatDate = elog_formatdatetime;
        let rend = Mustache.render(htmpl, ish);
        $("#glbl_modals_go_here").empty().append(rend);
        $("#glbl_modals_go_here").find(".modal").on("hidden.bs.modal", function(){ $("#glbl_modals_go_here").empty(); });
        $("#glbl_modals_go_here").find(".modal").modal("show");

    });
}

let actually_switch_station = function(){
    var exp_switch_info = $('#expswitch_choose_experiment table').data("selected-experiment");
    console.log("Switching " + exp_switch_info.instrument + " station " + exp_switch_info.station + " to experiment " + exp_switch_info.experiment_name);
    $("#expswitch_choose_experiment").modal("hide");
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
    .fail( function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); if(jqXHR.status == 403){ alert("You don't seem to have permissions for this operation. Please contact the site administrators."); return;}; alert("Server side exception switching experiment " + jqXHR.responseText); })
}

export function switch_experiment_on_station() {
    var instr = $(this).attr("data-instrument");
    var station = $(this).attr("data-station");
    console.log("Switching " + instr + "/" + station);
    Promise.all([fetch(new Request(experiments_by_instrument)), fetch(new Request("../../static/html/ops/switch/switch_modal.html"))])
    .then((resps) => {
        return Promise.all([resps[0].json(), resps[1].text()]);
    })
    .then((resps) => {
        let data = resps[0], mdltmpl = resps[1];
        $("#glbl_modals_go_here").empty().append(mdltmpl);
        $("#glbl_modals_go_here .expswitch_choose_experiment_title").text("Choose new experiment for " + instr + " Station: " + station + "");
        let experiments_for_instrument = _.filter(data.value[instr], function(x){ return !_.get(x, "is_locked", false)}),
            any_locked = _.some(data.value[instr], function(x){ return _.get(x, "is_locked", false)});
        if(any_locked) { $('#expswitch_choose_experiment .locked_warning').removeClass("d-none") } else { $('#expswitch_choose_experiment .locked_warning').addClass("d-none") }
        var rendered = Mustache.render(exper_template, {value: experiments_for_instrument});
        $("#glbl_modals_go_here table tbody").html(rendered);
        $('#glbl_modals_go_here table tbody tr').on('click', function(event) {
            $(this).find("td").addClass('rowselect');
            $(this).siblings().find("td").removeClass('rowselect');
            $('#glbl_modals_go_here table').data("selected-experiment", {instrument: instr, station: station, experiment_name: $(this).attr("data-expname")});
        });
        $("#glbl_modals_go_here #switch_experiment").on("click", actually_switch_station);
        $("#glbl_modals_go_here .modal").modal("show");
    })
}


export function put_instrument_in_standby() {
    var instr = $(this).attr("data-instrument");
    var station = $(this).attr("data-station");
    console.log("Putting " + instr + "/" + station + " into standby/maintenance mode.");
    $.ajax({
        type: "POST",
        contentType: "application/json; charset=utf-8",
        url: instrument_standby_url,
        data: JSON.stringify({"instrument": instr, "station": station}),
        dataType: "json"
    })
    .done(function(data){
        if(data.success) {
            console.log("Successfully put "+ instr + "/" + station + " into standby/maintenance mode.");
            location.reload();
        } else {
            alert("Server side exception switching experiment " + data.errormsg);
        }
    })
    .fail( function(jqXHR, textStatus, errorThrown) { alert("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
};
