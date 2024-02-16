let wf_job_tmpl = `<div class="row jobrow" data-jobid="{{_id}}"><span class="col-1"></span><span class="col-2">{{def.name}}</span><span class="col-1">{{status}}</span><span class="col-1">{{tool_id}}</span>
<span class="col-2"><span class="listview-action wact kill-job" title="Kill a running job" {{^running}}disabled{{/running}}><i class="fas fa-skull-crossbones"></i></span><span class="listview-action wact view-log" title="View the log file"><i class="fas fa-align-justify"></i></span><span class="listview-action wact view-details" title="View job details"><i class="fas fa-info-circle"></i></span><span class="listview-action wact delete-job" title="Delete this job entry" {{#running}}disabled{{/running}}><i class="fas fa-trash"></i></span></span><span class="col-5 wf_counters"><ul>{{#counters}}<li><span class="wf_counter_key">{{{key}}}</span>:<span class="wf_counter_value">{{{value}}}</span></li>{{/counters}}</ul></span></div>`,
wf_run_tmpl = `<div class="runrow" data-spgntr="{{num}}"><div class="row runhdr"><span class="col-1">{{num}}</span><span class="col-2"><select><option value=""> </option>{{#wf_defs}}<option value="{{.}}">{{.}}</option>{{/wf_defs}}</select></span></div>
<div class="jobsdiv">{{#jobs}}`+wf_job_tmpl+`{{/jobs}}</div></div>`;
Mustache.parse(wf_job_tmpl);Mustache.parse(wf_run_tmpl);

let kick_off_job = function() {
  let jobname = $(this).val(), run_num = $(this).closest(".runrow").attr("data-spgntr");
  $(this).closest(".runrow").find("select").val("");
  console.log("Kicking off job " + jobname + " for run " + run_num);
  $.ajax({ url: "ws/create_workflow_job", data: JSON.stringify({"job_name": jobname, "run_num": run_num}), type: "POST", contentType: "application/json; charset=utf-8", dataType: "json" })
  .done(function(data, textStatus, jqXHR) {
    if(data.success) {
        console.log("Successfully triggered job manually for " + jobname + " for run " + run_num);
    } else {
      error_message("Server side exception triggering job " + data.errormsg);
    }
  })
  .fail( function(jqXHR, textStatus, errorThrown) { error_message("Server side HTTP failure triggering job " + textStatus); })
}

let show_content_modal = function(title, content_url) {
  $.when($.ajax("../../static/html/ms/generic_msg.html"), $.ajax(content_url))
  .done(function(d0, d1) {
    if(d1[0].success) {
        let rendered = $(Mustache.render(d0[0], { title: title, message: "<pre>" + d1[0].value + "</pre>" }));
        $("#lcls_wf_ctrls_tab").find(".mdl_holder").empty().append(rendered);
        $("#lcls_wf_ctrls_tab").find(".mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#lcls_wf_ctrls_tab").find(".mdl_holder").empty(); });
        $("#lcls_wf_ctrls_tab").find(".mdl_holder").find(".modal").modal("show");
    } else {
      error_message("Server failure: " + data.errormsg);
    }
  })
  .fail( function(jqXHR, textStatus, errorThrown) { error_message("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
}
let kill_job = function() {
  $.getJSON("ws/kill_workflow_job", {"job_id": $(this).closest(".jobrow").attr("data-jobid")})
  .done(function(d){if(_.get(d, "success", false)){ success_message("Job was successfully killed"); } else { error_message("Error killing job " + _.get(d, "errormsg", ""))}})
  .fail(function(jqXHR, textStatus, errorThrown) { error_message("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
}
let view_log = function() {
  let jobid = $(this).closest(".jobrow").attr("data-jobid");
  show_content_modal("Log file for " + jobid, "ws/workflow/" + jobid + "/job_log_file");
}
let view_details = function() {
  let jobid = $(this).closest(".jobrow").attr("data-jobid");
  show_content_modal("Details for " + jobid, "ws/workflow/" + jobid + "/job_details");
}
let delete_job = function() {
  $.getJSON("ws/delete_workflow_job", {"job_id": $(this).closest(".jobrow").attr("data-jobid")}).fail( function(jqXHR, textStatus, errorThrown) { error_message("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
}
let job_attach_actions_fn = function(rendered) {
  rendered.find(".kill-job").not("[disabled]").on("click", kill_job);
  rendered.find(".view-log").not("[disabled]").on("click", view_log);
  rendered.find(".view-details").not("[disabled]").on("click", view_details);
  rendered.find(".delete-job").not("[disabled]").on("click", delete_job);
}
let job_render_fn = function(){
  let rendered = $(Mustache.render(wf_job_tmpl, this));
  job_attach_actions_fn(rendered);
  return rendered;
};
let run_render_fn = function(){
  let rendered = $(Mustache.render(wf_run_tmpl, this));
  rendered.find(".runhdr select").on("change", kick_off_job);
  job_attach_actions_fn(rendered);
  return rendered;
};


export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer alwaysreload lgbk_socketio" id="lcls_wf_ctrls_tab">
    <div class="mdl_holder"></div>
    <div class="container-fluid text-center" id="wf_ctrls_content">
      <div class="row ctrls_hdr"><span class="col-1">Run</span><span class="col-2">Job</span><span class="col-1">Status</span><span class="col-1">Job ID</span><span class="col-2">Actions</span><span class="col-5">Report</span></div>
      <div class="ctrls_content spgntr_append"></div>
    </div>
  </div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;


  sortable_paginator($("#wf_ctrls_content"), "num", "num", true, 0, 50, 50);
  $(window).scroll(function () {
      if ($(window).scrollTop() >= $(document).height() - $(window).height() - 10) {
          $("#wf_ctrls_content").data("spgntr").pageDown();
      }
  });

  $.when($.getJSON('ws/workflow_jobs'), $.getJSON('ws/runs?includeParams=false'), $.getJSON('ws/workflow_definitions'))
  .done(function(d0, d1, d2){
      let jobs = d0[0].value, runs = d1[0].value, wf_defs = _.map(d2[0].value, "name");
      _.each(jobs, function(x){ x.running = _.includes(["RUNNING", "SUBMITTED"], _.get(x, "status", ""))})
      let jobsbyrun = _.groupBy(jobs, function(x){ return x["run_num"]});
      _.each(runs, function(r){ r.jobs = _.get(jobsbyrun, r['num'], []); r.wf_defs = wf_defs; r.render = run_render_fn; });
      $("#wf_ctrls_content").data("spgntr").addObjects(runs);

      trgt.querySelector(".lgbk_socketio").addEventListener("runs", function(event){
          let rundoc = event.detail, rdoc = rundoc.value;
          rdoc.wf_defs = wf_defs;
          rdoc.render = run_render_fn;
          console.log("WS run update "); 
          console.log(rundoc);
          if(_.get(rundoc, "CRUD", null) != "Create") return;
          $("#wf_ctrls_content").data("spgntr").addObject(rdoc);
      });
  })


  trgt.querySelector(".lgbk_socketio").addEventListener("workflow_jobs", function(event){
    let wfjobdoc = event.detail, wfjobid = _.get(wfjobdoc, "value._id");
    if(_.isNil(wfjobid)) { console.log("Got a workflow_jobs without an _id"); console.log(wfjobdoc); return }
    if(wfjobdoc["CRUD"] == "Delete") {
      $("#wf_ctrls_content").find("[data-jobid="+wfjobid+"]").remove();
    } else {
      wfjobdoc["value"].running = _.includes(["RUNNING", "SUBMITTED"], _.get(wfjobdoc["value"], "status", ""));
      let rendered = $(Mustache.render(wf_job_tmpl, wfjobdoc["value"])); job_attach_actions_fn(rendered);
      if($("#wf_ctrls_content").find("[data-jobid="+wfjobid+"]").length <= 0) {
        console.log("WF jobs add new entry "); console.log(wfjobdoc);
        $("#wf_ctrls_content").find("[data-spgntr="+wfjobdoc["value"]["run_num"]+"]").find(".jobsdiv").prepend(rendered);
      } else {
        console.log("WF jobs update existing entry"); console.log(wfjobdoc);
        $("#wf_ctrls_content").find("[data-jobid="+wfjobid+"]").replaceWith(rendered);
      }
    }
  });

  let setUpToolbar = function() {
      var tab_toolbar = `<span id="wf_ctrls_run_range" title="Submit a job for multiple runs."><i class="fas fa-subway fa-lg"></i></span>`;
      var toolbar_rendered = $(tab_toolbar);
      console.log("Yamaguchi");
      $("#toolbar_for_tab").append(toolbar_rendered);
      $("#wf_ctrls_run_range").on("click", function(){
        $.when($.ajax('../../static/html/tabs/lcls/wf/jobs/lcls_wf_job_runs.html'), $.getJSON('ws/workflow_definitions'))
        .done(function(d0, d1) {
          let mdltext = d0[0], wf_job_names = _.map(d1[0].value, "name"), mdl_rendered = $(Mustache.render(mdltext, {wf_job_names: wf_job_names}));
          $("#lcls_wf_ctrls_tab").find(".mdl_holder").empty().append(mdl_rendered);
          mdl_rendered.find(".submit").on("click", function(){
            let gteqr = mdl_rendered.find(".range_start").val(), lteqr = mdl_rendered.find(".range_end").val(), jobname = mdl_rendered.find(".job_name").val();
            if((!_.isEmpty(gteqr) && !/[0-9]/.test(gteqr)) || (!_.isEmpty(lteqr) && !/[0-9]/.test(lteqr))) { error_message("Please specify integer run numbers"); return; }
            if((!_.isEmpty(gteqr) && !_.isEmpty(lteqr) && _.toNumber(lteqr) < _.toNumber(gteqr))) { error_message("Range start should be less than range end"); return; }
            if(_.isEmpty(jobname)){ error_message("Please specify a job name"); return; }
            let lowerLimitSpecified = !_.isEmpty(gteqr), lowerLimit = _.toNumber(gteqr), upperLimitSpecified = !_.isEmpty(lteqr), upperLimit = _.toNumber(lteqr);
            $.getJSON('ws/runs?includeParams=false').done(function(d0){
              var runs = _.map(d0.value, "num"); runs = _.filter(runs, function(r){ return !lowerLimitSpecified || r >= lowerLimit }); runs = _.filter(runs, function(r){ return !upperLimitSpecified || r <= upperLimit });
              _.each(runs, function(run){
                console.log("Submitting job for run " + run);
                $.ajax({ url: "ws/create_workflow_job", data: JSON.stringify({"job_name": jobname, "run_num": run }), type: "POST", contentType: "application/json; charset=utf-8", dataType: "json" })
                .done(function(data, textStatus, jqXHR) {
                  if(!data.success) { error_message("Server side exception triggering job for run " + run + " - " + data.errormsg)}
                }).fail( function(jqXHR, textStatus, errorThrown) { error_message("Server side HTTP failure triggering job " + textStatus + " for run " + run); })
              })
              $("#lcls_wf_ctrls_tab").find(".mdl_holder").find(".modal").modal("hide");
            })
          })
          $("#lcls_wf_ctrls_tab").find(".mdl_holder").find(".modal").modal("show");
          $("#lcls_wf_ctrls_tab").find(".mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#lcls_wf_ctrls_tab").find(".mdl_holder").empty(); });
        })
      });
  };

  setUpToolbar();
}