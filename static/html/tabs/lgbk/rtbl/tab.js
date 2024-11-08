let array_mean = function(arr) {
  return arr.reduce((acc, curr) => { return acc + curr}, 0) / arr.length;
} 
let array_std = function(arr) {
  // https://www.geeksforgeeks.org/how-to-get-the-standard-deviation-of-an-array-of-numbers-using-javascript/
  let mean = array_mean(arr);
  arr = arr = arr.map((k) => { return (k - mean) ** 2 });
  let sum = arr.reduce((acc, curr) => acc + curr, 0);
  let variance = sum / arr.length
  return Math.sqrt(sum / arr.length)
} 


let attach_toolbar_btns = function() { 
  var tab_toolbar = `<span id="new_rtbl" title="Create a new run table"><i class="fa-solid fa-plus fa-lg tlbr"></i></span>
  <span id="edit_rtbl" title="Edit this run table"><i class="fa-solid fa-edit fa-lg tlbr"></i></span>
  <span id="clone_rtbl" title="Clone this run table"><i class="fa-solid fa-clone fa-lg tlbr"></i></span>
  <span id="clone_tmpl" title="Clone system template run tables to this experiment"><i class="fa-solid fa-redo-alt"></i></span>
  <span id="del_rtbl" title="Delete this run table"><i class="fa-solid fa-trash fa-lg tlbr"></i></span>
  <span id="export_rtbl" title="Export this run table as a CSV"><i class="fa-solid fa-download fa-lg tlbr"></i></span>
  <span id="make_system_rtbl" title="Move this run table to the system run tables. These are visible to all experiments; the move will replace any system run table with the same name. This run table will be removed from this experiment."><i class="fa-solid fa-globe fa-lg tlbr"></i></span>
  `;
  var toolbar_rendered = $(tab_toolbar);
  if(!_.get(privileges, "ops_page", false)) { toolbar_rendered.find("#make_system_rtbl").remove(); }
  $("#toolbar_for_tab").append(toolbar_rendered);
  $("#new_rtbl").on("click", function(e) { $("#rtbl_tab").data("new_rtbl_fn")(e)});
  $("#edit_rtbl").on("click", function(e) { $("#rtbl_tab").data("edit_rtbl_fn")(e)});
  $("#export_rtbl").on("click", function(e) { $("#rtbl_tab").data("csv_rtbl_fn")(e)});
  $("#clone_rtbl").on("click", function(e) { $("#rtbl_tab").data("clone_rtbl_fn")(e)});
  $("#clone_tmpl").on("click", function(e) { $("#rtbl_tab").data("clone_template_run_tables_fn")(e)});
  $("#del_rtbl").on("click", function(e) { $("#rtbl_tab").data("del_rtbl_fn")(e)});
  $("#make_system_rtbl").on("click", function(e) { $("#rtbl_tab").data("make_system_rtbl")(e)});


  import("./rtbl_def_modal.js").then((mod) => {
    const col_defs_dialog = mod.col_defs_dialog;
    $("#rtbl_tab").data("new_rtbl_fn", function(e) { col_defs_dialog(); });
    $("#rtbl_tab").data("edit_rtbl_fn", function(e) { var clkRTblName = $("#rtbl_tab .nav-pills a.active").attr("data-rtbl-name"); col_defs_dialog(clkRTblName); });
  })
  import("./rtbl_fns.js").then((mod) => { 
    const { export_as_csv, delete_rtbl_fn, clone_rtbl_fn, clone_sys_tmpl_rtbls, make_system_runtable } = mod;
    $("#rtbl_tab").data("csv_rtbl_fn", export_as_csv);
    $("#rtbl_tab").data("del_rtbl_fn", delete_rtbl_fn);
    $("#rtbl_tab").data("clone_rtbl_fn", clone_rtbl_fn);
    $("#rtbl_tab").data("clone_template_run_tables_fn", clone_sys_tmpl_rtbls);
    $("#rtbl_tab").data("make_system_rtbl", make_system_runtable);  
  })
}

var run_tbl_pill_template = `{{#value}}<li class="nav-item"><a class="nav-link rtbl_pill {{#is_system_run_table}}rtbl_sys{{/is_system_run_table}}" data-bs-toggle="tab" data-rtbl-name="{{name}}" href="#{{name}}" title="{{description}}">{{ name }}</a></li>{{/value}}`;
var run_tbl_tbl = `<table class="table table-striped table-bordered table-hover table-condensed sticky-table"><thead></thead><tbody class="spgntr_append"></tbody></table>`;
Mustache.parse(run_tbl_pill_template);
Mustache.parse(run_tbl_tbl);
var rtnl_row_tmpl; // Set later below.

var update_editable_for_run = function( input_elem ) {
  console.log("Updating editable column");
  $.getJSON({ url: "ws/run_table_editable_update", method: "POST", data: { runnum: input_elem.attr('data-run-num'), source: input_elem.attr('data-column-source'), value: input_elem.text()}})
  .done(function(data, textStatus, jqXHR){ if(data.success) { console.log("Successfully updated editable");} else { alert("Server side exception updating editable " + data.errormsg); }})
  .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); alert("Server side exception updating editable " + jqXHR.responseText)});
}

/*
A div with the contenteditable attr is more flexible from a run table layout perspective.
However, this does not plugin to the jQuery change notification framework easily.
This shim will kick off a change event when the contenteditable has changed.
*/

var content_editable_trigger_change = function(rowRendered) {
  rowRendered.find("[contenteditable]").on('focus', function() {
      var $this = $(this);
      $this.data('before', $this.html());
      return $this;
  }).on('focusout', function() {
      var $this = $(this);
      if ($this.data('before') !== $this.html()) {
          $this.data('before', $this.html());
          $this.trigger('change');
      }
      return $this;
  });
}

var renderRunData = function() {
    this.FormatDate = elog_formatdatetime;
    var rowRendered = $(Mustache.render(rtnl_row_tmpl, this));
    rowRendered.find("td").hover(
      function(){ $("#rtbl_content thead").find("[data-col-idx=" + $(this).closest("td").index() + "]").addClass("tblhighlight"); },
      function(){ $("#rtbl_content thead").find("[data-col-idx=" + $(this).closest("td").index() + "]").removeClass("tblhighlight"); });
    content_editable_trigger_change(rowRendered);
    rowRendered.find(".rtbl_editable_column").change(function(){ update_editable_for_run($(this))});
    rowRendered.find("td").hover(function() { let colnum = parseInt($(this).index()) + 1; $(this).closest("table").find('td:nth-child(' + colnum + ')').addClass('rbtl_col_hvr'); }, function() { let colnum = parseInt($(this).index()) + 1; $(this).closest("table").find('td:nth-child(' + colnum + ')').removeClass('rbtl_col_hvr')});
    return rowRendered;
}

var renderTabularData = function(coldefs, runData, sampleData) { // Render a tabluar run data...
    var numHdrRows = _.find([[6, 1], [12, 2], [18, 3], [0, 4]], function(v) { return (v[0] == 0 || coldefs.length < v[0]); })[1];
    var tblRndr = $(Mustache.render(run_tbl_tbl, {}));
    var hdr = _.times(numHdrRows, function() { return $("<tr/>"); }), row_tmpl = "";
    _.each(coldefs, function(coldef, idx) {
      if(idx > 0 && idx < numHdrRows) { hdr[idx%numHdrRows].append($("<th colspan='" + idx + "' class='rtbl_filler'>&nbsp;</th>"))};
      hdr[idx%numHdrRows].append($("<th colspan='"+ numHdrRows + "' class='rtbl_header' data-col-idx='" + idx + "' >" + coldef["label"] + "</th>"));
      if(coldef["source"] == "Separator") {
        row_tmpl = row_tmpl + "<td class='rtbl_separator'>&nbsp;</td>";
      } else if (coldef["is_editable"]) {
        row_tmpl = row_tmpl + "<td><div class='rtbl_editable_column_parent'><div contenteditable='true' data-run-num='{{num}}' data-column-source='" + coldef["source"] + "' class='rtbl_editable_column' title='Type and click outside the box to update'>{{" + coldef["source"] + "}}</div></div></td>";
      } else if(_.get(coldef, "tickifpresent", false)) {
        row_tmpl = row_tmpl + "<td class='text-center'>{{#" + coldef["source"]  + "}}<span class='rtblbooltick'><i class='fa-solid fa-check'></i></span>{{/" + coldef["source"] + "}}</td>";
      } else if (_.endsWith(coldef["source"], "_time")) {
        row_tmpl = row_tmpl + "<td>{{#FormatDate}}{{" + coldef["source"] + "}}{{/FormatDate}}</td>";
      } else if (_.startsWith(coldef["mime_type"], "image/")) {
        row_tmpl = row_tmpl + "<td><img class='rtbl_thumbnail' src='{{" + coldef["source"] + "}}'></td>";
      } else {
        row_tmpl = row_tmpl + "<td>{{" + coldef["source"] + "}}</td>";
      }
    });
    tblRndr.find("thead").empty().append(hdr);
    tblRndr.data("samples", _.fromPairs(_.map(sampleData, function(o){return [o["_id"], o["name"]]})));
    $("#rtbl_content").html(tblRndr);
    sortable_paginator($("#rtbl_content").find("table"), "num", "num", true, 0, 400, 50);
    rtnl_row_tmpl = "<tr data-runnum={{num}} data-spgntr={{num}}>" + row_tmpl + "</tr>";

    Mustache.parse(rtnl_row_tmpl);
    _.each(runData, function(r){ r.render = renderRunData})
    $("#rtbl_content").find("table").data("spgntr").addObjects(runData);
    var thead_top = $("#rtbl_content .sticky-table thead")[0].getBoundingClientRect().top;
    $.each($("#rtbl_content .sticky-table thead th"), function(){
        $(this).css({"top": $(this)[0].getBoundingClientRect().top - thead_top + "px"});
    })
    $(window).scroll(function () {
      if ($(window).scrollTop() >= $(document).height() - $(window).height() - 10) {
        if(!_.isNil($("#rtbl_content").find("table").data("spgntr"))) {
          $("#rtbl_content").find("table").data("spgntr").pageDown();
        }
    }});
}


let allotherlogicfb = function(trgt) {


  $.getJSON("ws/run_tables")
  .done(function(tblData){
    _.each(tblData.value, function(tdef){
      tdef.coldefs = _.sortBy(tdef.coldefs, function(v){ return v["position"];});
      tdef.coldefs.unshift({"label": "Run", "source": "num", "is_editable": false, "position": -1 })
    });
    tblData.value = _.reject(tblData.value, function(x){ return _.get(x, "is_template", false)});
    $("#rtbl_tab").data("tblData", _.keyBy(tblData.value, function(o) {  return o.name; }));
    console.log($("#rtbl_tab").data("tblData"));
    var rendered = $(Mustache.render(run_tbl_pill_template, tblData));
    $("#rtbl_tab .nav-pills").append(rendered);
    rendered.find(".rtbl_pill").on("click", function() {
      let clkRTblName = $(this).attr("data-rtbl-name");
      console.log("Getting data for run table " + clkRTblName);
      sessionStorage['runtable_active_tab'] = clkRTblName;
      let tblDef = $("#rtbl_tab").data("tblData")[clkRTblName], coldefs = tblDef.coldefs;
      let rtbl_data_params = {"tableName": clkRTblName}, binCount = _.get(tblDef, "bin_count", 100);
      if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples") { rtbl_data_params["sampleName"] = sample_showing_in_UI; }
      $("#lgbk_body").addClass("busy");
      $.when($.getJSON("ws/run_table_data", rtbl_data_params), $.getJSON("ws/samples"))
      .done(function(d0, d1){
        let runData = d0[0], sampleData = d1[0], hide_outliers=false, plotlyExists = false;
          if(_.includes(["histogram", "scatter", "generatedscatter"], _.get(tblDef, "table_type"))) {
            $.when($.ajax({ url: "../../js/plotly.js/dist/plotly.min.js", dataType: "script", cache: true }), $.getJSON({ url: "../../static/json/fapaths.json", cache: true }))
            .done(function(d0, d1){
                var plotlyDivName = _.get(tblDef, "name") + '_plotlydiv', faicons = d1[0];
                $("#rtbl_content").html("<div id='" + plotlyDivName + "'></div>");
                var traces = [], layout = {}, gen_traces;
                if(_.get(tblDef, "table_type") == "histogram") {
                    layout = { barmode: "overlay", title: { text: clkRTblName }, xaxis: { title: { text: _.head(_.tail(tblDef.coldefs))["label"], xref: "paper" }}};
                    gen_traces = function() {
                      traces = [];
                      _.each(_.tail(coldefs), function(coldef, idx) {
                        var dt = _.map(runData.value, function(rd){ var ret = _.get(rd, coldef["source"]); if(/^([0-9.]+)$/.test(ret)) { ret = _.toNumber(ret); } return ret; });
                        if(hide_outliers) {
                          let sd = Plotly.d3.deviation(dt), mean = Plotly.d3.mean(dt), mult = 3.0;
                          let isOutlier = function(v) { return (v >= mean + (mult * sd)) | (v <= mean - (mult * sd)); };
                          dt = _.reject(dt, isOutlier);
                        }
                        traces.push({x: dt, type: "histogram", showlegend: true, name: coldef["label"]});
                        if(!_.isEmpty(_.get(tblDef, "bin_size"))) {
                          _.last(traces)['xbins'] = {start: _.min(_.last(traces)['x']), end: _.max(_.last(traces)['x'])};
                          let computedBinSize = ((_.last(traces)['xbins']['end'] - _.last(traces)['xbins']['start'])/binCount);
                          _.last(traces)['xbins']['size'] = (_.isFinite(computedBinSize) && _.has(tblDef, "bin_size")) ? _.get(tblDef, "bin_size") : computedBinSize;
                          console.log("Bin Size" + _.last(traces)['xbins']['size']);
                        }
                        });
                      }
                } else if ((_.get(tblDef, "table_type") == "scatter") || (_.get(tblDef, "table_type") == "generatedscatter")) {
                  if(_.get(tblDef, "table_type") == "generatedscatter") { 
                    coldefs = _.concat(coldefs, [{ "label": "Run", "type": "Run Info", "source": "num"}], _.map(_.uniq(_.flatten(_.map(_.map(runData.value, "params"), _.keys))).sort(), function(x){ return { "label": x, "source": "params." + x } }))
                  }
                  console.log(coldefs);
                  var xaxissrc = _.head(_.tail(coldefs))["source"], isdatetime = (_.endsWith(xaxissrc, "_time"));
                  let xaxissrcepoch = isdatetime ? xaxissrc + "_epoch" : xaxissrc;
                  let dateformatfn = isdatetime ? function(d) { if(_.has(d, xaxissrcepoch)) {return new Date(_.get(d, xaxissrcepoch))} else {return new moment(_.get(d, xaxissrc)).toDate()}} : function(d) { return _.get(d, xaxissrc) };
                  var xaxisdata = _.map(runData.value, function(rd){return dateformatfn(rd)});
                  gen_traces = function() {
                    traces = [];
                    _.each(_.tail(_.tail(coldefs)), function(coldef, idx) {
                      var dtx = xaxisdata.slice();
                      var dty = _.map(runData.value, function(rd){return _.get(rd, coldef["source"])});
                      let customData = runData.value;
                      let sd = array_std(dty), mean = array_mean(dty), mult = 3.0;
                      let isYOutlier = function(v, idx) { return (dty[idx] >= mean + (mult * sd)) | (dty[idx] <= mean - (mult * sd)); };
                      let isOutlier = function(v) { return (v >= mean + (mult * sd)) | (v <= mean - (mult * sd)); };
                      if(hide_outliers) {dtx = _.reject(dtx, isYOutlier); dty = _.reject(dty, isOutlier);}
                      traces.push({x: dtx, y: dty, type: "scatter", mode: "markers", showlegend: true, name: coldef["label"], customdata: customData, hovertemplate: "%{x} %{y}<br><b>Run number:</b> %{customdata.num}"});
                    });
                  }
                  layout = { title: { text: clkRTblName }, xaxis: { title: { text: _.head(_.tail(coldefs))["label"], xref: "paper" }}};
                  if(coldefs.length == 3){ layout["yaxis"] = { title: { text: _.last(coldefs)["label"], yref: "paper" }} }
                }
                layout["height"] = $(window).height() - ( $("#myNavRow").height() + $(".tab_title_bar").height() + $(".nav-pills").height() + $("#lgbk_footer").height() + 40);
                gen_traces();
                let plotConfig = {displaylogo: false, modeBarButtonsToRemove: ['sendDataToCloud'], modeBarButtonsToAdd: [
                  { name: 'Hide show outliers', icon: faicons["solid/compact-disc"], click: function() { hide_outliers = !hide_outliers; console.log("Outliers: " + hide_outliers); gen_traces(); Plotly.react(plotlyDivName, traces, layout, plotConfig); }}
                ]};
                if(plotlyExists) { Plotly.react(plotlyDivName, traces, layout, plotConfig); } else { Plotly.newPlot(plotlyDivName, traces, layout, plotConfig); plotlyExists = true; }
                document.getElementById(plotlyDivName).on('plotly_hover', function(data){ console.log(data) });
                return;
        })
      }
        if (_.get(tblDef, "table_type") == "groupbytable") {
            let mcd = _.tail(tblDef["coldefs"]), mrd = runData.value, scs = _.map(mcd, "source"), justvals = _.map(mrd, function(x){ return _.pick(x, scs) }), uniqvals = _.uniqWith(justvals, _.isEqual)
            _.each(uniqvals, function(uq){ uq["runs"] = []})
            _.each(mrd, function(r) {
                _.each(uniqvals, function(u) {
                    if(_.isEqual(_.pick(r, scs), _.pick(u, scs))) {
                        u["runs"].push(r["num"])
                        return false;
                    }
                })
            })
            uniqvals = _.reverse(_.sortBy(uniqvals, scs));
            _.each(uniqvals, function(uq, idx){ uq["num"] = idx})
            renderTabularData(_.concat(mcd, [{is_editable: false, label: "Runs", mime_type: "TEXT", position: mcd.length, source: "runs", type: "Run Info"}]), uniqvals, sampleData.value);
            return;
        }
        if (_.get(tblDef, "table_type") == "generatedtable") {
            let tickifpresent = !_.get(tblDef, "showvalues", true);
            coldefs = _.concat(coldefs, _.map(_.uniq(_.flatten(_.map(_.map(runData.value, "params"), _.keys))).sort(), function(x){ return { "label": x, "source": "params." + x, "tickifpresent": tickifpresent } }))
            if(tickifpresent) { _.each(runData.value, function(x){ _.each(_.keys(_.get(x, "params", {})), function(k){_.set(x, "params."+k, true)})})  }
        }
        renderTabularData(coldefs, runData.value, sampleData.value);
      })
      .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); alert("Server side exception getting data " + jqXHR.responseText)})
      .always(function(){ $("#lgbk_body").removeClass("busy"); })

      if(_.get(privileges, "post", false)) {
          $("#toolbar_for_tab").find(".tlbr").show();
          $("#make_system_rtbl").hide();
          if(_.get(tblDef, 'is_system_run_table', false)) {
              $("#edit_rtbl").hide(); $("#make_system_rtbl").hide();
          } else {
              if(_.get(privileges, "ops_page", false)) {
                  $("#make_system_rtbl").show();
              }
              $("#edit_rtbl").show();
          }
      } else {
          $("#toolbar_for_tab").find(".tlbr").hide();
      }
    });

    rendered.find( _.has(sessionStorage, 'runtable_active_tab') ? ("[data-rtbl-name='" + sessionStorage['runtable_active_tab'] + "']") : ".rtbl_pill").first().addClass("active").trigger("click");
    sessionStorage.removeItem("runtable_active_tab");

    trgt.querySelector(".lgbk_socketio").addEventListener("runs", function(event){
      let runData = event.detail;
      console.log(runData);
      console.log("Processing web socket event for run " + runData.value['num'] + " for experiment " + runData['experiment_name'] + " CRUD=" + runData["CRUD"]);
      var tblRndr = $("#rtbl_content").find("table"), runSample = _.get(runData.value, 'sample', "");
      if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples" && runSample != sample_showing_in_UI) { console.log("Skipping updating run table for different sample " + runSample); return; }
      runData.value.render = renderRunData;
      let clkRTblName = $("#rtbl_tab .nav-pills a.active").attr("data-rtbl-name"), tblDef = $("#rtbl_tab").data("tblData")[clkRTblName], coldefs = tblDef.coldefs;
      if (_.get(tblDef, "table_type") == "generatedtable") {
          let tickifpresent = !_.get(tblDef, "showvalues", true);
          coldefs = _.concat(coldefs, _.map(_.uniq(_.flatten(_.map(_.map(runData.value, "params"), _.keys))).sort(), function(x){ return { "label": x, "source": "params." + x, "tickifpresent": tickifpresent } }))
          if(tickifpresent) { _.each([runData.value], function(x){ _.each(_.keys(_.get(x, "params", {})), function(k){_.set(x, "params."+k, true)})})  }
      } else if(_.get(tblDef, "table_type") == "groupbytable") {
          let mcd = _.tail(tblDef["coldefs"]), scs = _.map(mcd, "source"), curr_run_key = _.map(runData.value, scs), disp_objs = $("#rtbl_content").find("table").data("spgntr").disp_objs;
          let existing_uniq_obj = _.find(disp_objs, function(dobj){ return _.isEqual(_.pick(runData.value, scs), _.pick(dobj, scs))});
          if(_.isNil(existing_uniq_obj)) {
              let new_uniq_obj = _.assign(_.pick(runData.value, scs), {"runs": [runData.value["num"]], "num": disp_objs.length + 1});
              new_uniq_obj.render = renderRunData;
              $("#rtbl_content").find("table").data("spgntr").addObject(new_uniq_obj);
          } else {
              existing_uniq_obj["runs"] = _.uniq(_.concat(existing_uniq_obj["runs"], [runData.value["num"]])).sort().reverse();
              $("#rtbl_content").find("table").data("spgntr").addObject(existing_uniq_obj);
          }
          return;
      } else if(_.get(tblDef, "table_type", "table") == "table") {
        $("#rtbl_content").find("table").data("spgntr").addObject(runData.value);
      }
    });

    $("#rtbl_tab").on("lg.refreshOnSampleChange", function() {
        $("#rtbl_tab").find(_.has(sessionStorage, 'runtable_active_tab') ? ("[data-rtbl-name='" + sessionStorage['runtable_active_tab'] + "']") : ".rtbl_pill").first().trigger("click");
    });
  });

}


export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer lgbk_socketio" id="rtbl_tab"><ul class="nav nav-pills"></ul> <div class="mdl_holder"></div><div class="container-fluid text-start" id="rtbl_content"></div></div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;

  allotherlogicfb(trgt);
  attach_toolbar_btns();  
}
