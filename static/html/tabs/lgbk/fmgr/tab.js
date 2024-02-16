let allotherfunctionality = function(trgt) {
    var file_main_templ = `<div class="fdat" data-entry-id="{{ _id }}" data-spgntr="{{run_num}}" ><div class="row">
    <div class="col-md-2 fmfi"><span class="fmgr-expand exp_icons_left"><i class="fas fa-plus expand_ctrl"></i></span>{{ run_num }}</div><div class="col-md-3 text-start">{{ num_files }}</div><div class="col-md-2 text-start">{{ hrsize }}</div><div class="col-md-2"></div>
    <div class="col"><div class="row align-items-center d-flex flex-wrap">{{#fstat}}{{#visible}}<div class="locbtngrp" data-loc-name={{name}} title="According to the system, {{#all}}all{{/all}}{{^all}}{{#some}}some{{/some}}{{^some}}no{{/some}}{{/all}} files are estimated to be present at this location. Please use the check now button to get a current picture of file availability. Please use the restore button to make files available at this location."><span>
            <button class="runloc-btn refresh pl-1 pr-1 checknow {{#all}}all_files{{/all}}{{^all}}{{#some}}some_files{{/some}}{{^some}}no_files{{/some}}{{/all}}" data-restore="false">Check now</button>
            <button class="runloc-btn restore pl-1 pr-1 {{#all}}all_files{{/all}}{{^all}}{{#some}}some_files{{/some}}{{^some}}no_files{{/some}}{{/all}}" data-restore="true">Restore</button>
        </span></div>{{/visible}}{{/fstat}}</div></div></div></div>`;

var fmgr_child_template = `<div class="row col-md-12 fmgr-chid"><div class="card w-100"><div class="card-body">
    {{#files}}<div class="row run_file" data-file-path="{{path}}"><div class="col-md-5 text-start fmgr_exp_file_name">{{ trunc_path }}</div><div class="col-md-2 text-start">{{ hrsize }}</div><div class="col-md-2 text-start">{{#FormatDate}}{{ create_timestamp }}{{/FormatDate}}</div>
    </div>{{/files}}</div></div></div>`;
var fmgr_file_types_locs_tmpl = `<span class='fmgr_type_label col-2'>For file restores, please select the types of files you wish to restore: </span><span class="col-2">{{#ftypes}}<input class="ft_chkbx" type="checkbox" id="ft_{{name}}" data-ftype="{{name}}" {{#selected}}checked{{/selected}}><label for="ft_{{name}}" title="{{tooltip}}">{{label}}</label>{{/ftypes}}</span>
{{^locslen}}<span class='fmgr_locs_label col-3'>No data management locations have been associated with this experiment. Please contact LCLS data management to correct this.</span>{{/locslen}}{{#locslen}}<span class='fmgr_locs_label col-2'>Please choose a location where you wish to restore the file:</span>{{/locslen}}<span class="col-4">{{#locs}}<input class="loc_chkbx" type="radio" id="loc_{{name}}" value="{{name}}" name="location" {{#selected}}checked{{/selected}}><label for="ft_{{name}}">{{name}}</label>{{/locs}}</span>`;

Mustache.parse(file_main_templ);
Mustache.parse(fmgr_child_template);
Mustache.parse(fmgr_file_types_locs_tmpl);

var expandFunction = function() {
   var run_files =  $(this).closest(".fdat").data("run_files");
   console.log(run_files);
   if($(this).hasClass("fmgr-expanded")) {
       $(this).closest(".fdat").find(".fmgr-chid").remove();
       $(this).html('<i class="fas fa-plus expand_ctrl"></i>');
   } else {
       var clicked_elem = $(this);
       run_files.files = _.sortBy(run_files.files, function(fl){ return fl['path']});
       let rendered = renderMSTemplate(fmgr_child_template, run_files);
       clicked_elem.closest(".fdat").append(rendered);
       $(this).html('<i class="fas fa-minus expand_ctrl"></i>');
     }
     $(this).toggleClass("fmgr-expanded");
};

var renderMSTemplate = function(template, entry) { // Convienience method to render time correctly.
    entry.FormatDate = elog_formatdatetime;
    return $(Mustache.render(template, entry));
}

var run_loc_click = function() {
    let run_num = $(this).closest("[data-spgntr]").attr("data-spgntr"), loc_name = $(this).closest("[data-loc-name]").attr("data-loc-name"), restore_files = ($(this).attr("data-restore") == "true");
    let file_types_to_restore = _.join($("#fmgr_tab .fmgr_types").find("[data-ftype]:checked").map(function(){ return $(this).attr("data-ftype"); }).toArray(), ",");
    if(_.isEmpty(file_types_to_restore)) { error_message("Please select at least one file type to restore"); return; }
    console.log("Clicked on " + run_num + " for location " + loc_name + " restore files " + restore_files + " types " + file_types_to_restore);
    $.when($.getJSON("ws/check_and_move_run_files_to_location", {run_num: run_num, location: loc_name, restore_missing_files: restore_files, file_types_to_restore: file_types_to_restore}), $.ajax("../../static/html/ms/filemgr_status.html"))
    .done(function(d0, d1){
        if(d0[0].success) {
            _.each(d0[0].value["run_files"], function(f){ $(document).trigger('file_catalog',[{"value": f}]); })
            console.log(d0[0]);
            if(restore_files) { info_message("A request has been issued to the data mover to restore these files"); return; }
            let total_files = d0[0].value["matching_files"].length, files_by_status = _.countBy(_.values(d0[0].value["dmstatus"]), _.identity), present_files = _.get(files_by_status, "present", 0),  pending_files = _.get(files_by_status, "pending", 0), restore_on = ((total_files - ( pending_files + present_files)) > 0);
            var rendered = $(Mustache.render(d1[0], {title: "Status of files for run " + run_num + " at " + loc_name, message: "Of the " + total_files + " <i>" + file_types_to_restore +  "</i> files in run " + run_num + "<ul><li>" + present_files + " are already present at " + loc_name + "</li><li>" + pending_files + " are in the data mover queues</li></ul>", restore_on: restore_on}));
            rendered.find(".restore_btn").on("click", function(){
                $.getJSON("ws/check_and_move_run_files_to_location", {run_num: run_num, location: loc_name, restore_missing_files: true, file_types_to_restore: file_types_to_restore})
                .done(function(){
                    console.log("Restore kicked off.");
                    $("#fmgr_tab").find(".mdl_holder").find(".modal").modal("hide");
                }).fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure " + textStatus); })
            });
        } else {
            var rendered = $(Mustache.render(d1[0], {title: "Status of files for run " + run_num + " at " + loc_name, message: d0[0].errormsg, restore_on: restore_on}));
        }
        $("#fmgr_tab").find(".mdl_holder").empty().append(rendered);
        $("#fmgr_tab").find(".mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#lcls_wf_ctrls_tab").find(".mdl_holder").empty(); });
        $("#fmgr_tab").find(".mdl_holder").find(".modal").modal("show");
    })
    .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure " + textStatus); })
}

var human_readable_size = function(size_in_bytes) {
    if(_.isNil(size_in_bytes)){ return "N/A"; }
    var units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"];
    var hr = size_in_bytes;
    for (var i = 0; i < units.length; i++) {
        if(_.inRange(hr, 0, 1001)) { return hr.toFixed(2) + " " + units[i]; }
        hr = hr/1024;
    }
    return size_in_bytes + " bytes";
}
var dm_locations;
var prep_run_file = function(run) {
    let rf =  {run_num: run["num"], num_files: 0, total_size: 0, files: [], dm_locations: dm_locations, fstat: _.map(dm_locations, function(x){ return { name: x, all: false, some: false }}) };
    rf.render = function() {
        this.updateStat();
        var rendered = renderMSTemplate(file_main_templ, this);
        rendered.data("run_files", rf);
        rendered.find(".fmgr-expand").on("click", expandFunction);
        rendered.find(".runloc-btn").on("click", run_loc_click);
        return rendered;
    }
    let matchfpat = function(f) { let fpats = $("#fmgr_tab").data("ftype_patterns"); return _.some(fpats, function(p){ return (new RegExp(p)).test(f.path)})};
    rf.updateStat = function() {
        let selectedloc = $("#fmgr_tab").find("input[name=location]:checked").val();
        let rf = this, matfiles = _.filter(rf.files, matchfpat)
        _.forOwn(rf.fstat, function(v,k,o){ o[k].all = matfiles.length != 0 && _.every(_.map(matfiles, "dm_locations." + k + ".present"))});
        _.forOwn(rf.fstat, function(v,k,o){ o[k].some = matfiles.length != 0 && _.some(_.map(matfiles, "dm_locations." + k + ".present"))});
        _.forOwn(rf.fstat, function(v,k,o){ o[k].visible = (selectedloc == v["name"])});
        rf.num_files = rf.files.length;
        rf.total_size = _.sum(_.map(rf.files, function(f){return _.get(f, "size", 0)}));
        rf.hrsize = human_readable_size(rf.total_size);
    }
    return rf;
}
var add_file_to_run_files = function(file, run_files) {
    if(_.isNil(run_files)) { console.log("Cannot find run files for " + file["run_num"]); return; }
    file.dm_locations = _.map(run_files.dm_locations, function(x){ return {name : x, present: _.includes(_.keys(_.get(file, "locations")), x), "asof": _.get(file, "locations."+x+".asof")}});
    file.trunc_path = (file.path.length < 64) ? file.path : "..." + file.path.substr(-64) ;
    file.hrsize = human_readable_size(file.size);
    run_files.files.push(file);
}

let process_file_types = function(fmgr_file_types) {
    $("#fmgr_tab").data("ftype_patterns", ".*");
    if(!_.isEmpty(fmgr_file_types)) {
        let ftype_rdr = $(Mustache.render(fmgr_file_types_locs_tmpl, { ftypes: _.values(fmgr_file_types), locs: _.map(dm_locations, function(l, i){ return { name: l, selected: (i==0)}}), locslen: dm_locations.length }));
        $("#fmgr_tab .fmgr_types").empty().append(ftype_rdr);
        let fpat = function() { $("#fmgr_tab").data("ftype_patterns", _.flatten(_.concat(_.map(_.filter(fmgr_file_types, function(ft){ return $("#fmgr_tab .fmgr_types").find("[data-ftype="+ft["name"]+"]").is(":checked")}), function(ft){ return ft["patterns"]; }))))};
        $("#fmgr_tab .fmgr_types").find(".ft_chkbx").on("change", function(){ fpat(); $("#fmgr_content").data("spgntr").redraw(); })
        fpat();
        let floc = function() { $("#fmgr_tab .exp_tab_header").find(".current_location").empty().append($("#fmgr_tab").find("input[name=location]:checked").val()); }
        $("#fmgr_tab .fmgr_types").find(".loc_chkbx").on("change", function(){ floc(); $("#fmgr_content").data("spgntr").redraw(); })
        floc();
      }
}

let reload_page = function() {
    let getrunparams = { includeParams: false };
    if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples") { getrunparams["sampleName"] = sample_showing_in_UI; }
    $.when($.getJSON("ws/files", getrunparams), $.getJSON("ws/runs", getrunparams), $.getJSON('ws/dm_locations'), $.getJSON('../filemanager_file_types'))
    .done(function(d0, d1, d2, d3){
        dm_locations = _.map(d2[0].value, "name");
        const fmgr_file_types = d3[0].value;
        process_file_types(fmgr_file_types);
        let files = _.fromPairs(_.map(d1[0].value, function(x){ return [x["num"], prep_run_file(x)]}));
        _.each(d0[0].value, function(file) { add_file_to_run_files(file, files[file["run_num"]]) });
       sortable_paginator($("#fmgr_content"), "run_num", "run_num", true, 0, 400, 50);
       $("#fmgr_content").data("spgntr").addObjects(_.values(files));
    });
}
reload_page();

trgt.querySelector(".lgbk_socketio").addEventListener("runs", function(event){
    console.log("WS run update "); 
    let rundoc = event.detail;
    console.log(rundoc);
    let runSample = _.get(rundoc.value, 'sample', "");
    if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples" && runSample != sample_showing_in_UI) { console.log("Skipping updating file manager for run from a different sample " + runSample); return; }
    let rf = prep_run_file(rundoc.value);
    fetch("ws/"+rf["run_num"]+"/files")
    .then((resp) => { return resp.json(); })
    .then((filesresp) => {
        _.each(filesresp.value, function(file) { add_file_to_run_files(file, rf) });
        $("#fmgr_content").data("spgntr").addObject(rf);
    })
})

trgt.querySelector(".lgbk_socketio").addEventListener("file_catalog", function(event){
    let fdoc = event.detail, run_num = fdoc.value["run_num"], run_files = $("#fmgr_content").find("[data-spgntr="+run_num+"]").data("run_files");
    if(!_.isNil(run_files)) {
        console.log("WS file_catalog update "); console.log(fdoc); console.log(run_files);
        _.remove(run_files.files, ["path", fdoc.value["path"]]);
        add_file_to_run_files(fdoc.value, run_files)
        $("#fmgr_content").data("spgntr").addObject(run_files);
    } else {
        console.log("Probably skipping file_catalog update for a different sample as the run does not exist");
    }
});
$("#fmgr_tab").on("lg.refreshOnSampleChange", function() {
    reload_page();
});
$(window).scroll(function () {
    if ($(window).scrollTop() >= $(document).height() - $(window).height() - 10) {
        $("#fmgr_content").data("spgntr").pageDown();
    }
});

let setUpToolbar = function() {
    var tab_toolbar = `<span id="check_now_for_all_runs" title="Check the file system now for the presence of files for all runs."><i class="fas fa-sync fa-lg tlbr"></i></span>`;
    var toolbar_rendered = $(tab_toolbar);
    $("#toolbar_for_tab").append(toolbar_rendered);
    $("#check_now_for_all_runs").on("click", function(e) {
      let file_types_to_restore = _.join($("#fmgr_tab .fmgr_types").find("[data-ftype]:checked").map(function(){ return $(this).attr("data-ftype"); }).toArray(), ",");
      if(_.isEmpty(file_types_to_restore)) { error_message("Please select at least one file type to restore"); return; }
      $("#fmgr_content .checknow").each(function(){
        let btn = $(this), run_num = $(this).closest("[data-spgntr]").attr("data-spgntr"), run_files = $(this).closest("[data-spgntr]").data("run_files"), loc_name = $(this).closest("[data-loc-name]").attr("data-loc-name");
        btn.closest(".row").find("button").removeClass(["all_files", "some_files", "no_files"]);
        $.getJSON("ws/check_and_move_run_files_to_location", {run_num: run_num, location: loc_name, restore_missing_files: false, file_types_to_restore: file_types_to_restore})
        .done(function(fcheck){
          run_files.files = [];
          _.each(_.get(fcheck, "value.run_files", []), function(fdoc){
            _.remove(run_files.files, ["path", fdoc["path"]]);
            add_file_to_run_files(fdoc, run_files)
          })
          $("#fmgr_content").data("spgntr").addObject(run_files);

          let files_present = _.values(_.get(fcheck, "value.dmstatus", {}));
          if(_.every(files_present)) { btn.closest(".row").find("button").addClass("all_files") }else { if(_.some(files_present)) { btn.closest(".row").find("button").addClass("some_files") } else { btn.closest(".row").find("button").addClass("no_files") }};
        }).fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure " + textStatus); })
      })
    });
};
setUpToolbar();
}

export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer lgbk_socketio" id="fmgr_tab"><div class="mdl_holder"></div>
    <div class="text-start fmgr_types row"></div>
    <div class="text-start" id="fmgr_content">
    <div class="exp_tab_header">
        <div class="row"><div class="col-md-2 fmfi">Run</div><div class="col-md-3">File</div><div class="col-md-2">Size</div><div class="col-md-2">Created</div><div class="col-md-3">Location <span class="current_location"></span></div></div>
        <div class="row"><div class="col-md-2"></div><div class="col-md-3"></div><div class="col-md-2"></div><div class="col-md-2"></div><div class="col-md-3 locnameshdr"></div></div>
    </div>
    <div class="spgntr_append"></div>
    </div></div>
    `;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

    allotherfunctionality(trgt);
}