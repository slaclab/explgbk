var exper_template = `{{#value}}<tr data-expid="{{_id}}">
<td> <a target="_blank" href="{{_id}}/">{{ name }}</a> </td>
<td> {{ instrument }} </td>
<td> {{#FormatDate}}{{first_run.begin_time }}{{/FormatDate}} </td>
<td> {{#FormatDate}}{{last_run.begin_time}}{{/FormatDate}} </td>
<td> {{ run_count }} </td>
<td> {{#FormatDate}}{{file_timestamps.first_file_ts }}{{/FormatDate}} </td>
<td> {{#FormatDate}}{{file_timestamps.last_file_ts}}{{/FormatDate}} </td>
<td> {{ file_timestamps.hr_duration }} </td>
<td> {{#FormatNum}}{{ totalDataSize }}{{/FormatNum}} </td>
<td> {{ contact_info }} </td>
<td> {{ leader_account }} </td>
</tr>{{/value}}`;
Mustache.parse(exper_template);

var display_experiments = function() {
    var sorted_exps = _.sortBy($("#exp_summary_tab").data("experiments"), $("#exp_summary_tab").data("cur_sort_attr"));
    if(!$("#exp_summary_tab").data("cur_sort_desc")) { sorted_exps = _.reverse(sorted_exps); }
    var expdata = { value: sorted_exps };
    expdata.FormatDate = elog_formatdate;
    expdata.FormatNum = function() { return function(numLiteral, render) { var num = render(numLiteral); return _.toNumber(num).toFixed(2)}};
    var rendered = Mustache.render(exper_template, expdata);
    $("#exp_summary_tab tbody").html(rendered);
}


export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="exp_summary_tab">
    <div class="row">
        <div id="exp_mdl_holder"></div>
        <div class="table-responsive">
            <table class="table table-condensed table-striped table-bordered">
                <thead><tr>
                    <th data_attr="name">Name<i class="fas fa-sort-down sric"></i></th>
                    <th data_attr="instrument">Instrument</th>
                    <th data_attr="first_run.begin_time">First Run</th>
                    <th data_attr="last_run.begin_time">Last Run</th>
                    <th data_attr="run_count">Number of runs</th>
                    <th data_attr="file_timestamps.first_file_ts">First File</th>
                    <th data_attr="file_timestamps.last_file_ts">Last File</th>
                    <th data_attr="file_timestamps.duration">Duration</th>
                    <th data_attr="totalDataSize">Total data(GB)</th>
                    <th data_attr="contact_info">PI</th>
                    <th data_attr="leader_account">Leader Account</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    </div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

    $.when($.getJSON({ url: experiments_url }), $.getJSON({ url: instruments_url }))
    .done(function(d0, d1) {
      var experiments = d0[0].value, instruments = _.keyBy(d1[0].value, "_id");
      $("#exp_summary_tab").data("experiments", experiments);
      $("#exp_summary_tab").data("instruments", instruments);
      $("#exp_summary_tab").data("cur_sort_attr", "name");
      $("#exp_summary_tab").data("cur_sort_desc", true);

      $("#exp_summary_tab th[data_attr]").on("click", function() {
          var curr_attr = $("#exp_summary_tab").data("cur_sort_attr");
          var sel_attr = $(this).attr("data_attr");
          if(curr_attr == sel_attr) {
              $("#exp_summary_tab").data("cur_sort_desc", !$("#exp_summary_tab").data("cur_sort_desc"));
              $(this).closest("th").find(".sric").remove();
          } else {
              $("#exp_summary_tab").data("cur_sort_attr", sel_attr)
              $("#exp_summary_tab").data("cur_sort_desc", true);
              $(this).closest("thead").find(".sric").remove();
          }
          $(this).closest("th").append($("#exp_summary_tab").data("cur_sort_desc") ? $('<i class="fas fa-sort-down sric"></i>') : $('<i class="fas fa-sort-up sric"></i>'))
          display_experiments();
      });

      display_experiments();
  })
}

