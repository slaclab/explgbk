    import { new_entry_click, followup_function, edit_elog_entry } from "./elog_new_entry.js";
    
    var elog_header = `<div class="row exp_tab_header">
     <div class="col-2">Posted</div>
     <div class="col-1">Run</div>
     <div class="col-5">Content</div>
     <div class="col-3">Tags</div>
     <div class="col-1">Author</div>
    </div><div class="spgntr_append"></div>`;
    var elog_main_template = `<div class="edat {{^root}}etop{{/root}}{{#root}}edesc{{/root}}" id="{{ elem_id }}" data-spgntr="{{elem_id}}"><div class="row">
     <div class="col-2">
       <span class="elog-expand elog-compressed exp_icons_left"><i class="fa-solid fa-plus expand_ctrl"></i></span>
       {{#c_attach}}<span class="exp_icons_left"><i class="fa-solid fa-paperclip expand_ctrl"></i></span>{{/c_attach}}
       {{#FormatDate}}{{ relevance_time }}{{/FormatDate}}
     </div>
     <div class="col-1" title="{{run_num}}">{{ run_num_str }}</div>
     {{> main_content_tmpl }}
     <div class="col-1 text-start">{{ author }}</div>
     </div></div>`;
     var elog_main_content_template = `<div class="col-5 elog_main_cnt text-start text_truncate {{#deleted_by}}elog_deleted{{/deleted_by}} ">{{#title}}{{title}}{{/title}}{{^title}}{{ content }}{{/title}}</div><div class="col-3 elog_main_cnt">{{#src_expname}}{{.}}{{#tagcount}}|{{/tagcount}}{{/src_expname}}{{#tags}}<span class="elog_tag">{{.}}</span>{{/tags}}</div>`;
   
    var elog_child_template = `<div class="row col-12 elog-chid">
      <div class="card">
       <div class="card-header text-start"><span class="entry_actions">{{^deleted_by}}<span class="followup" title="Followup"><i class="fa-solid fa-paper-plane fa-lg"></i></span>{{#privileges.edit}}<span class="edit" title="Edit"><i class="fa-solid fa-edit fa-lg"></i></span>{{^parent}}<span class="ins_elogs" title="Post to instrument elogs"><i class="fa-solid fa-mail-bulk fa-lg"></i></span><span class="get_link" title="Open this entry in a new tab"><i class="fa-solid fa-external-link-alt fa-lg"></i></span>{{/parent}}<span class="delete" title="Delete"><i class="fa-solid fa-trash fa-lg"></i></span>{{/privileges.edit}}{{/deleted_by}}</span>{{#title}}<div class="chid_title">{{title}}</div><div class="chid_content">{{{content}}}</div>{{/title}}{{^title}}<pre class="precontent">{{content}}</pre>{{/title}}</div>
       <div class="card-body">
         {{> elog_chid_body_content }}
        <div class="row dialog_holder"></div>
       </div>
      </div>
    </div>`;
    var elog_chid_body_content = `<div class="elog_chid_body_content">{{#deleted_by}}<div class="row elog_deleted_by">Deleted by {{deleted_by}} - {{#FormatDate}}{{ deleted_time }}{{/FormatDate}}</div>{{/deleted_by}}
    <div class="row">{{#attachments}}<div class="col-3"><a href="ws/attachment?entry_id={{entry_id}}&attachment_id={{_id}}&prefer_preview=False" target="_blank" class="thumbnail"><img class="elog_img" src="ws/attachment?entry_id={{entry_id}}&attachment_id={{_id}}&prefer_preview=true"></img></a></div>{{/attachments}}</div></div>`;
   
   
   
     var elog_run_main_template = `<div class="edat etop" id="{{ elem_id }}" data-runnum="{{num}}" data-spgntr="{{elem_id}}"><div class="row">
          <div class="col-2">
            <span class="elog-expand elog-compressed exp_icons_left"><i class="fa-solid fa-plus expand_ctrl"></i></span>
            {{#FormatDate}}{{relevance_time}}{{/FormatDate}}
          </div>
          <div class="col-1" title="{{num}}">{{ run_num_str }}</div>
          <div class="elog_main_cnt col-5 text_truncate">{{ content }}</div>
          </div></div>`;
   
      var elog_run_child_template = `<div class="row col-12 elog-chid">
        <div class="card">
         <div class="card-header text-start"><span class="entry_actions"><span class="change_sample" title="Change the sample that this run is associated with"><i class="fa-solid fa-snowflake fa-lg"></i></span></div>
         <div class="card-body">
           {{#param_list}}
             <div class="elog_run_param_category text-start" data-category="{{k}}"><span class="expand_param expand_plus"><i class="fa-solid fa-plus"></i></span>{{k}}<div class="elog_run_params_expanded"></div></div>
           {{/param_list}}
           {{^param_list}}<div class="text-start">This run has no params</div>{{/param_list}}
         </div>
        </div>
      </div>`;
   
      var elog_run_child_expanded_params_template = `<table class="table table-condensed table-striped table-bordered"><thead><tr><th>Name</th><th>Value</th><th>Description</th></tr></thead><tbody>{{#params}}<tr><td>{{l}}</td><td>{{v}}</td><td>{{d}}</td></tr>{{/params}}</tbody></table>`;
   
   
      var id2entry = {};
      var skip_websocket_elog_messages = false;
      var in_search_results = false;
   
     Mustache.parse(elog_main_template);
     Mustache.parse(elog_main_content_template);
     Mustache.parse(elog_child_template);
     Mustache.parse(elog_chid_body_content);
     Mustache.parse(elog_run_main_template);
     Mustache.parse(elog_run_child_template);
     Mustache.parse(elog_run_child_expanded_params_template);

      
     var renderMSTemplate = function(template, entry, partials) { // Convienience method to render time correctly.
       entry.FormatDate = elog_formatdatetime;
       return $(Mustache.render(template, entry, partials));
     }
   
   
    var delete_elog_entry = function() {
        var entry = $(this).closest(".edat").data("entry");
        $.getJSON({url: "ws/delete_elog_entry?_id="+encodeURIComponent(entry["_id"]), method: "DELETE" })
        .done(function(){})
        .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); alert("Server side exception deleting elog entry " + jqXHR.responseText); })
    }
   
    var post_to_instrument_elogs = function() {
        var entry = $(this).closest(".edat").data("entry");
        $.when($.ajax('../../static/html/ms/choose_few_of_many.html'), $.getJSON("ws/get_instrument_elogs")).done(function(d0, d1){
            var instrument_elogs = d1[0].value, choose_tmpl = d0[0]; Mustache.parse(choose_tmpl);
            if(_.isEmpty(instrument_elogs)) { alert("There are no elogs configured for this instrument."); return; }
            instrument_elogs = _.difference(instrument_elogs, _.get(entry, "post_to_elogs", []));
            if(_.isEmpty(instrument_elogs)) { alert("All related elogs seem to have this entry"); return; }
            var rendered = renderMSTemplate(choose_tmpl, { title: "Cross-post this entry to these related elogs", submit_label: "Post", choices: instrument_elogs });
            rendered.find(".c_f_o_m_submit").on("click", function(){
                var post_to_elogs = $("#elog_tab").find(".mdl_holder").find(".modal").find("input:checked").map(function() { return $(this).attr("name"); }).toArray();
                console.log(post_to_elogs);
                $("#elog_tab").find(".mdl_holder").find(".modal").modal("hide");
                if(!_.isEmpty(post_to_elogs)) {
                    $.getJSON({url: "ws/cross_post_elogs", data: {_id: entry["_id"], post_to_elogs: _.join(post_to_elogs, ",") }})
                    .done(function(){})
                    .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); error_message("Server side exception cross posting elog entry " + jqXHR.responseText); })
                }
            })
            $("#elog_tab").find(".mdl_holder").append(rendered);
            $("#elog_tab").find(".mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#elog_tab").find(".mdl_holder").empty(); });
            $("#elog_tab").find(".mdl_holder").find(".modal").modal();
        })
    }
   
    var open_entry_in_new_window = function() {
      var entry = $(this).closest(".edat").data("entry");
      window.open("elogs/" + entry["_id"], name="_blank");
    }
   
    var expandFunction = function() {
       var entry = $(this).closest(".edat").data("entry"), expdr = $(this).find(".elog-expand");
       console.log("Expand/contract " + entry["_id"]);
       if(expdr.hasClass("elog-expanded")) {
           $(this).closest(".edat").find(".elog-chid").remove();
           expdr.html('<i class="fa-solid fa-plus expand_ctrl"></i>');
       } else {
           var clicked_elem = $(this);
           entry.privileges = privileges;
           clicked_elem.closest(".edat").append(renderMSTemplate(elog_child_template, entry, { elog_chid_body_content: elog_chid_body_content } ));
           clicked_elem.closest(".edat").find(".followup").on("click", followup_function);
           clicked_elem.closest(".edat").find(".delete").on("click", delete_elog_entry);
           clicked_elem.closest(".edat").find(".edit").on("click", edit_elog_entry);
           clicked_elem.closest(".edat").find(".ins_elogs").on("click", post_to_instrument_elogs);
           clicked_elem.closest(".edat").find(".get_link").on("click", open_entry_in_new_window)
           _.each(_.sortBy(_.map(entry["c_children"], function(chid) { return $("#elog_tab").data("entries")[chid]; }), function(s) { return s["relevance_time"]; }).reverse(), function(ch_entry) {
               var rendered = renderMSTemplate(elog_main_template, ch_entry, { main_content_tmpl: elog_main_content_template });
               rendered.data("entry", ch_entry).data("ts", moment(ch_entry["relevance_time"]));
               clicked_elem.closest(".edat").find(".card-body").append(rendered);
               rendered.find(".elog-expand").closest(".row").on("click", expandFunction);
           });
           expdr.html('<i class="fa-solid fa-minus expand_ctrl"></i>');
       }
       expdr.toggleClass("elog-expanded elog-compressed");
    };
   
    var runExpandFunction = function() {
        var entry = $(this).closest(".edat").data("entry"), expdr = $(this).find(".elog-expand");
        console.log("Expand/contract run " + entry["num"]);
        if(expdr.hasClass("elog-expanded")) {
            $(this).closest(".edat").find(".elog-chid").remove();
            expdr.html('<i class="fa-solid fa-plus expand_ctrl"></i>');
        } else {
            var clicked_elem = $(this);
            $.when($.getJSON("ws/run_table_sources"), $.getJSON("ws/runs/"+entry["num"]))
            .done(function(d0, d1) {
                let param_defs = d0[0];
                entry["params"] = _.get(d1[0], "value.params", {});
                // src2catdesc is a flattened dict of arrays of dicts into a dict indexed by the source attribute.
                var src2catdesc = _.fromPairs(_.map(_.flatten(_.concat(_.values(param_defs.value))), function(pd) { return [_.replace(pd['source'], "params.", ""), { category: pd['category'], description: pd['description'], label: pd['label']}]})), categorized_params = {};
                _.each(entry["params"], function(v, k){
                    var category = _.get(src2catdesc, k + ".category", "Misc"), desc = _.get(src2catdesc, k + ".description", "N/A"), label = _.get(src2catdesc, k + ".label", k);
                    _.defaults(categorized_params, _.fromPairs([[category,[]]]))[category].push({k: k, v: v, d: desc, l: label});
                })
                var cat_params_list = _.sortBy(_.map(categorized_params, function(v, k){ return {k: k, v: v}}), function(o){return o['k']});
                var rendered = renderMSTemplate(elog_run_child_template, { param_list: cat_params_list });
                rendered.find(".expand_param").parent().on("click", function(ev){
                    console.log(ev);
                    if(!$(ev.target).hasClass("expand_param") && !$(ev.target).hasClass("elog_run_param_category") && !$(ev.target).is("path") && !$(ev.target).is("svg")) return;
                    var clickedElem = $(this), rexpdr = clickedElem.find(".expand_param");
                    if(rexpdr.hasClass("expand_plus")) {
                        var paramsrendered = renderMSTemplate(elog_run_child_expanded_params_template, { params: _.sortBy(categorized_params[clickedElem.attr("data-category")], function(o){ return o['k']})});
                        clickedElem.find(".elog_run_params_expanded").append(paramsrendered);
                        rexpdr.find("svg").replaceWith($('<i class="fa-solid fa-minus"></i>'));
                    } else {
                        clickedElem.find(".elog_run_params_expanded").empty();
                        rexpdr.find("svg").replaceWith($('<i class="fa-solid fa-plus"></i>'));
                    }
                    rexpdr.toggleClass("expand_plus")
                });
                rendered.find(".change_sample").on("click", function(){
                    let run_num = $(this).closest(".edat").attr("data-runnum");
                    $.when($.ajax('../../static/html/ms/choose_one_of_many.html'), $.getJSON("ws/samples"))
                    .done(function(d0, d1){
                        let tmpl = d0[0], smpls = _.map(d1[0].value, "name"); Mustache.parse(tmpl);
                        if(smpls.length == 0) {
                            error_message("This experiment does not have any samples defined.");
                            return;
                        }
                        let csrndrd = $(Mustache.render(tmpl, {title: "Please choose the sample that run " + run_num + " is to be associated with", choices: smpls, submit_label: "Change"}));
                        csrndrd.find(".c_o_o_m_submit").on("click", function(){
                            let chosensmpl = $(this).closest(".modal").find(".c_o_o_n_select").val();
                            if(!_.isEmpty(chosensmpl)) {
                                console.log("Need to change " + run_num + " to sample " + chosensmpl);
                                $.getJSON("ws/change_sample_for_run", {sample_name: chosensmpl, run_num: run_num})
                                .done(function(data){
                                    if(!data.success) {
                                        error_message("Server side exception changing sample for run " + data.errormsg);
                                    }
                                })
                                .fail(function(jqXHR, textStatus, errorThrown) { error_message("Server side exception changing sample for run " + jqXHR.responseText); })
                            }
                            $("#elog_tab").find(".mdl_holder").find(".modal").modal("hide");
                        })
                        $("#elog_tab").find(".mdl_holder").append(csrndrd);
                        $("#elog_tab").find(".mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#elog_tab").find(".mdl_holder").empty(); });
                        $("#elog_tab").find(".mdl_holder").find(".modal").modal();
                    })
                })
                clicked_elem.closest(".edat").append(rendered);
                expdr.html('<i class="fa-solid fa-minus expand_ctrl"></i>');
            });
        }
        expdr.toggleClass("elog-expanded elog-compressed");
    };
   
     var replaceExistingElogEntryContent = function(existingElem) { // If we get a update for an edit over web socker, we replace the contents of the elog entry.
         existingElem.find(".elog_main_cnt").replaceWith(renderMSTemplate(elog_main_content_template, this));
         if(_.has(this, "title")) {
             existingElem.find(".elog-chid").first().find(".chid_title").text(this["title"]);
             existingElem.find(".elog-chid").first().find(".chid_content").html($(this["content"]));
         } else {
             existingElem.find(".elog-chid pre").first().text(this["content"]);
         }
         existingElem.find(".elog_chid_body_content").first().replaceWith(renderMSTemplate(elog_chid_body_content, this));
     }
   
     var elogEntryRenderFunction = function() {
         var rendered = renderMSTemplate(elog_main_template, this, { main_content_tmpl: elog_main_content_template })
         rendered.data("entry", this).data("ts", moment(this["relevance_time"]));
         rendered.find(".elog-expand").closest(".row").on("click", this.expandFunction);
         return rendered;
     }
   
     var runRenderFunction = function() {
         var rendered = renderMSTemplate(elog_run_main_template, this);
         rendered.data("entry", this).data("ts", moment(this["relevance_time"]));
         rendered.find(".elog-expand").closest(".row").on("click", this.expandFunction);
         return rendered;
     }
   
     var truncateMiddle = function(x) {
         let strv = _.toString(x);
         if (strv.length > 10) {
             return strv.substr(0,5) + "..." +  strv.substr(strv.length-5);
         }
         return strv;
     }
   
     var processElogEntry = function(entry) {
         var root = _.get(entry, "root", null), parent = _.get(entry, "parent", null), attachments = _.get(entry, "attachments", null);
         if(attachments != null) {
             entry["c_attach"] = true;
             _.each(attachments, function(attachment) { attachment["entry_id"] = entry["_id"]; });
         }
         entry["run_num_str"] = truncateMiddle(entry["run_num"]);
         entry.render = elogEntryRenderFunction;
         entry.replaceExistingElogEntryContent = replaceExistingElogEntryContent;
         entry.expandFunction = expandFunction;
         entry.tagcount = _.get(entry, "tags", []).length;
         entry["elem_id"] = entry["_id"];
         entry["r_time"] = (new Date(entry["relevance_time"])).getTime();
         entry["emails_str"] = _.join(_.get(entry, "email_to", []), " ");
         id2entry[entry["_id"]] = entry;
     }
   
     var attach_children = function() {
         _.each(id2entry, function(entry, key){
             var myid = entry["_id"], root = _.get(entry, "root", null), parent = _.get(entry, "parent", null);
             if(parent != null && _.has(id2entry, parent)) {
                 var pey = id2entry[parent];
                    _.defaults(pey, {"c_children": []});
                    pey["c_children"] = _.union(pey["c_children"], [ entry["_id"] ]);
             }
             if(root != null && _.has(id2entry, root)) {
                 var rey = id2entry[root];
                    _.defaults(rey, {"c_desc": []});
                    rey["c_desc"] = _.union(rey["c_desc"], [ entry["_id"] ]);
             }
         });
     }
   
   
     var processElogResponse = function(data) {
       _.each(data.value, function(entry) { processElogEntry(entry); });
       attach_children();
       return data.value;
     };
   
     var processRunResponse = function(data) {
         if(!_.get(window, "showRuns", true)) { return [] };
         var runEntries = [];
         var addRunEntry = function(run, run_end) { // If run_end is true; we insert a stop event.
             var runData = _.clone(run);
             runData["run_num_str"] = truncateMiddle(runData["num"]);
             runData["elem_id"] = "r_"+runData["_id"]+ (run_end==true ? "_e" : "_b");
             runData["relevance_time"] = (run_end==true ? runData['end_time'] : runData['begin_time']);
             runData["r_time"] = (new Date(runData["relevance_time"])).getTime();
             runData["content"] = (run_end==true ? "Stop" : "Start");
             runData.render = runRenderFunction;
             runData.replaceExistingElogEntryContent = function() {};
             runData.expandFunction = runExpandFunction;
             runEntries.push(runData);
         }
         _.each(data.value, function(runData) {
             addRunEntry(runData, false);
             if (_.get(runData, "end_time", null) != null) { addRunEntry(runData, true) };
         });
         return runEntries;
     }
   
     var renderElogResponse = function(data) {
         $("#elog_content").html(elog_header);
         sortable_paginator($("#elog_content"), "elem_id", "r_time", true, 0, 100, 100);
         $("#elog_content").data("spgntr").addObjects(_.filter(data.value, function(f) { return !_.has(f, "root") }));
         if(!_.isNil($("#elog_content").data("spgntr").disp_objs) && $("#elog_content").data("spgntr").disp_objs.length > 0) { $("#elog_expand_all").removeClass("d-none"); } else { $("#elog_expand_all").addClass("d-none"); }
     }
   
   
   
     var load_elog_function = function() {
         var elog_params = {includeParams: false};
         if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples") { elog_params["sampleName"] = sample_showing_in_UI; }
         $("#elog_content").html('<div class="loading">Loading</div>');
         $.when($.getJSON("ws/elog", elog_params), $.getJSON("ws/runs", elog_params))
         .done(function(d1, d2){
             var elogData = d1[0], runData = d2[0];
             skip_websocket_elog_messages = false;
             renderElogResponse({value: _.concat(processElogResponse(elogData), processRunResponse(runData))});
             if(!_.isNil(sessionStorage.getItem("eLog_scrollTo"))) {
                 let scrollToId = sessionStorage.getItem("eLog_scrollTo");
                 console.log("Scrolling to entry " + scrollToId);
                 sessionStorage.removeItem("eLog_scrollTo");
                 $("#elog_content").data("spgntr").scrollTo(scrollToId);
                 let topElem = $("#elog_content").find("[data-spgntr=" + scrollToId + "]");
                 for (let i = 0; i < 25; i++) { topElem.find(".elog-compressed").trigger("click"); }
             }
         });
     };


   
     let search_text_input = function(e) {
         let search_text = $("#elog_search_text").val(), tag_sel = _.trim($("#elog_select_by_tag").val()), srchparams = {};
         if(!_.isEmpty(tag_sel)) { srchparams["tag"] = tag_sel; }
         let srchandrender = function(){ $.getJSON({ url: "ws/search_elog", data: srchparams}).done(function(data){ skip_websocket_elog_messages = true; in_search_results = true; processElogResponse(data); renderElogResponse(data); }); }
         if (!_.isNil(search_text)) {
             if(/^[0-9]+$/g.test(search_text)) {
                 _.assign(srchparams, { run_num : search_text });
             } else if(/^([0-9]+)-([0-9]+)$/g.test(search_text)) {
                 var start_run_num = /^([0-9]+)-([0-9]+)$/g.exec(search_text)[1];
                 var end_run_num   = /^([0-9]+)-([0-9]+)$/g.exec(search_text)[2];
                 _.assign(srchparams, { start_run_num : start_run_num, end_run_num: end_run_num });
             } else if(/^\d{1,2}[\/.]\d{1,2}[\/.]\d{4}$/.test(search_text) && moment(search_text, "MM/DD/YYYY").isValid()) {
                 _.assign(srchparams, { start_date : moment(search_text, "MM/DD/YYYY").subtract(1, "days").toJSON(), end_date : moment(search_text, "MM/DD/YYYY").add(1, "days").toJSON() });
             } else if(/^\d{1,2}[\/.]\d{1,2}[\/.]\d{4}-\d{1,2}[\/.]\d{1,2}[\/.]\d{4}$/.test(search_text) && moment(_.split(search_text, "-")[0], "MM/DD/YYYY").isValid() && moment(_.split(search_text, "-")[1], "MM/DD/YYYY").isValid()) {
                 _.assign(srchparams, { start_date : moment(_.split(search_text, "-")[0], "MM/DD/YYYY").subtract(1, "days").toJSON(), end_date : moment(_.split(search_text, "-")[1], "MM/DD/YYYY").add(1, "days").toJSON() });
             } else if(search_text.length > 2) {
                 _.assign(srchparams, { search_text : search_text });
             } else if(!_.isEmpty(tag_sel)) { } // Do nothing...
             else {
                 if(in_search_results) { $("#elog_tab").data("refresh")(); } in_search_results = false; return;
             }
             srchandrender();
         } else {
             if(in_search_results) { $("#elog_tab").data("refresh")(); }; in_search_results = false; return;
         }
     };
   
     let elog_attachments_only = function() {
         console.log("Getting data for attachments only");
         var elog_params = {includeParams: false};
         if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples") { elog_params["sampleName"] = sample_showing_in_UI; }
         $("#elog_content").html('<div class="loading">Loading</div>');
         $.getJSON("ws/elog", elog_params)
         .done(function(d0){
             let attachments_only_template = `<div class="row elog_attachments_only">{{#attachments}}<div class="img-thumbnail img-fluid atch" data-entryid="{{entry_id}}" data-id="{{_id}}" data-rootid="{{root_id}}" {{#isimage}}data-isimage="true">{{/isimage}}<span class="thumbnail"><img class="elog_img" src="ws/attachment?entry_id={{entry_id}}&attachment_id={{_id}}&prefer_preview=true"></img></span></div>{{/attachments}}</div>`;
             let entries = d0.value;
             Mustache.parse(attachments_only_template);
             let attachments_flat_list = [];
             _.each(entries, function(entry) {
                 if(_.has(entry, 'attachments')) {
                     _.each(entry.attachments, function(attachment){
                         attachment["entry_id"] = entry["_id"];
                         attachment["root_id"] = _.get(entry, "root", _.get(entry, "parent", entry["_id"]));
                         if(_.startsWith(_.get(attachment, "type", ""), "image/")) { attachment["isimage"] = true; }
                         attachments_flat_list.push(attachment);
                     });
                 }
             });
             attachments_flat_list = attachments_flat_list.reverse();
             let rendered = $(Mustache.render(attachments_only_template, { attachments: attachments_flat_list}));
             rendered.find(".atch").on("click", function(){
               let attchovrlytmpl = `<div id="elog_attch_ovrly" data-attchid="{{attchid}}"><img class="elog_img img-fluid" src="ws/attachment?entry_id={{entryid}}&attachment_id={{attchid}}"></img><div class="float-right ovrlytlbr">
                 <span class="gotoentry" title="Open this entry in a new tab."><span class="fa-layers fa-fw"><i class="fa-solid fa-circle" style="color:black"></i><i class="fa-solid fa-external-link-alt fa-lg" data-fa-transform="shrink-8"></i></span></span>
                 <span class="preventry" title="Display the previous attachment"><span class="fa-layers fa-fw"><i class="fa-solid fa-circle" style="color:black"></i><i class="fa-inverse fa-solid fa-chevron-up" data-fa-transform="shrink-6"></i></span></span>
                 <span class="nextentry" title="Display the next attachment"><span class="fa-layers fa-fw"><i class="fa-solid fa-circle" style="color:black"></i><i class="fa-inverse fa-solid fa-chevron-down" data-fa-transform="shrink-6"></i></span></span>
                 <span class="close"><span class="fa-layers fa-fw"><i class="fa-solid fa-circle" style="color:black"></i><i class="fa-inverse fa-solid fa-times" data-fa-transform="shrink-6"></i></span></span>
               </div></div>`;
               let entryid = $(this).attr("data-entryid"), attchid = $(this).attr("data-id"), rootid = $(this).attr("data-rootid");
               if(_.isEmpty($(this).attr("data-isimage"))) {
                 window.open("ws/attachment?entry_id=" + entryid + "&attachment_id=" + attchid, name="_blank");
                 return;
               }
               Mustache.parse(attchovrlytmpl); let rendered = $(Mustache.render(attchovrlytmpl, { attchid: attchid, entryid: entryid }))
               $("#elog_tab").find(".mdl_holder").after(rendered);
               $(document).on("keyup", function(e) { if (e.keyCode == 27) { $("#elog_attch_ovrly").remove() } });
               rendered.find(".close").on("click", function(){ $("#elog_attch_ovrly").remove(); })
               rendered.find(".gotoentry").on("click", function(){ $("#elog_attch_ovrly").remove(); sessionStorage.setItem("eLog_scrollTo", rootid); window.location.reload(true);
                 $("#elog_content").data("spgntr").scrollTo(rootid);
                 $("#elog_content").find("[data-spgntr=" + rootid + "] .elog-expand").trigger("click");
               })
               rendered.find(".preventry").on("click", function(){ let current_attach_id = $("#elog_attch_ovrly").attr("data-attchid"), prevElem = $("#elog_tab").find('[data-id="' + current_attach_id + '"]').prev(); $("#elog_attch_ovrly").remove(); if(!_.isNil(prevElem)) { prevElem.trigger("click"); } })
               rendered.find(".nextentry").on("click", function(){ let current_attach_id = $("#elog_attch_ovrly").attr("data-attchid"), nextElem = $("#elog_tab").find('[data-id="' + current_attach_id + '"]').next(); $("#elog_attch_ovrly").remove(); if(!_.isNil(nextElem)) { nextElem.trigger("click"); } })
             })
             $("#elog_content").html(rendered);
         });
     }
   
     let elog_hybrid_mode = function() {
         console.log("Attachments in hybrid mode.");
         var elog_params = {includeParams: false};
         if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples") { elog_params["sampleName"] = sample_showing_in_UI; }
         $("#elog_content").html('<div class="loading">Loading</div>');
         $.when($.getJSON("ws/elog", elog_params), $.getJSON("ws/runs", elog_params))
         .done(function(d0, d1){
             let attachments_only_template = `<div class="elog_hybrid_mode">{{#attachments}}<div class="row elog_hybrid_row"><div class="col-2">{{#run}}<div class="row"><span class="pl-2 pr-1"><strong>Run:</strong></span>{{run.num}}<span class="tblr runsync" title="Go to this run in the logbook" data-runid="{{run._id}}"><i class="fa-solid fa-sync"></i></span></div><div class="row"><span class="pl-2 pr-1"><strong>Run start:</strong></span>{{#FormatDate}}{{ run.begin_time }}{{/FormatDate}}</div>{{/run}}</div>
             <div class="col-2"><div class="row"><span class="pr-1"><strong>Author:</strong></span>{{entry.author}}</div><div class="row"><span class="pr-1"><strong>Posted:</strong></span>{{#FormatDate}}{{ entry.relevance_time }}{{/FormatDate}}<span class="tblr elogsync" title="Go to this entry in the logbook" data-elogid="{{entry._id}}"><i class="fa-solid fa-sync"></i></span></div><div class="row"><span class="pr-1"><strong>Name:</strong></span>{{name}}</div><div class="row"><span class="pr-1"><strong>Type:</strong></span>{{type}}</div></div>
             <div class="col"><a href="elogs/{{entry._id}}" class="thumbnail"><img class="elog_img" src="ws/attachment?entry_id={{entry._id}}&attachment_id={{_id}}&prefer_preview=true"></img></a></div></div>{{/attachments}}</div>`;
             Mustache.parse(attachments_only_template);
             let entries = d0[0].value, runs = _.keyBy(d1[0].value, "num");
             let attachments_flat_list = [];
             _.each(entries, function(entry) {
                 if(_.has(entry, 'attachments')) {
                     _.each(entry.attachments, function(attachment){
                         attachment["entry"] = entry;
                         if(_.has(entry, "run_num")) { attachment["run"] = runs[entry["run_num"]]  }
                         attachments_flat_list.push(attachment);
                     });
                 }
             });
             let atl = { attachments: attachments_flat_list.reverse()};
             atl.FormatDate = elog_formatdatetime;
             let rendered = $(Mustache.render(attachments_only_template, atl));
   
             rendered.find(".elogsync").on("click", function(){
                 sessionStorage.setItem("eLog_scrollTo", $(this).attr("data-elogid"));
                 location.reload();
             })
             rendered.find(".runsync").on("click", function(){
                 sessionStorage.setItem("eLog_scrollTo", "r_" + $(this).attr("data-runid") + "_b");
                 location.reload();
             })
             $("#elog_content").empty().html(rendered);
         });
     }

let attach_toolbar_btns = function() {
    var tab_toolbar = `<select id="elog_select_by_tag" class="d-none"><option value="">Select by tag</option></select>
    <input type="text" placeholder="Search/Run etc - see tooltip" title='Search;"A phrase";Author;Tag;Run;Run-Run;date(MM/DD/YYYY);date-date;x:Regex' id="elog_search_text">
    <span id="elog_new_entry"><i class="fa-solid fa-plus fa-lg" title="Post a new elog entry"></i></span>
    <span id="elog_toggle_runs"><i class="fa-solid fa-running fa-lg" title="Hide/show run entries"></i></span>
    <span id="elog_expand_all" class="d-none"><i class="fa-solid fa-arrows-alt fa-lg" title="Expand all visible entries"></i></span>
    <span id="elog_attachments_only"><i class="fa-solid fa-paperclip fa-lg" title="Toggle attachments only"></i></span>
    <span id="elog_hybrid_mode"><i class="fa-solid fa-table fa-lg" title="Attachments as a table (aka hybrid mode)"></i></span>
    <span id="elog_deleted_entries"><i class="fa-solid fa-strikethrough fa-lg" title="Toggle deleted entries"></i></span>
    <span class="d-none" id="elog_daq_ami_issue"><i class="fa-solid fa-bug fa-lg" title="Log a DAQ/AMI issue in the computing log; provides context and timing to PCDS personnel."></i></span>
    <span id="elog_email_subscribe"><i class="fa-solid fa-inbox fa-lg" title="Automatically receive email notifications"></i></span>`;
    var toolbar_rendered = $(tab_toolbar);
    $("#toolbar_for_tab").append(toolbar_rendered);
    $.getJSON("ws/get_elog_tags").done(function(d0){
        $("#elog_select_by_tag").append(Mustache.render(`{{#.}}<option value="{{.}}">{{.}}</option>{{/.}}`, d0.value)).removeClass("d-none");
        $("#elog_select_by_tag").on("change", search_text_input);
    })
    $("#elog_new_entry").on("click", new_entry_click);
    $("#elog_attachments_only").on("click", function() {
        if($("#elog_attachments_only").hasClass("pushedin")) {
            $("#elog_tab").data("refresh")();
            skip_websocket_elog_messages = false;
        } else {
            elog_attachments_only();
            skip_websocket_elog_messages = true;
        }
        $("#elog_attachments_only").toggleClass("pushedin");
    });
    $("#elog_hybrid_mode").on("click", function() {
        if($("#elog_hybrid_mode").hasClass("pushedin")) {
            $("#elog_tab").data("refresh")();
            skip_websocket_elog_messages = false;
        } else {
            elog_hybrid_mode();
            skip_websocket_elog_messages = true;
        }
        $("#elog_hybrid_mode").toggleClass("pushedin");
    });
    $("#elog_toggle_runs").on("click", function() {
        window.showRuns = !_.get(window, "showRuns", true);
        $("#elog_tab").data("refresh")();
    });
    $("#elog_expand_all").on("click", function(){ $("#elog_content").find(".elog-expand").closest(".row").trigger("click") })
    $("#elog_deleted_entries").on("click", function() {
        if($("#elog_deleted_entries").hasClass("pushedin")) {
            $("#elog_tab").find(".elog_deleted").closest(".edat").removeClass("d-none");
        } else {
            $("#elog_tab").find(".elog_deleted").closest(".edat").addClass("d-none");
        }
        $("#elog_deleted_entries").toggleClass("pushedin");
    });
    $("#elog_email_subscribe").on("click", function(){
        $.when($.ajax('../../static/html/ms/elog_email_subscriptions.html'), $.getJSON("ws/elog_email_subscriptions"))
        .done(function(mdltxt, emls){
            var email_subscription_modal = mdltxt[0], email_subscribers = emls[0].value, current_user_subscription = _.find(email_subscribers, ['subscriber', logged_in_user]);
            Mustache.parse(email_subscription_modal);
            var rendered = $(Mustache.render(email_subscription_modal, {experiment_name: experiment_name, logged_in_user: logged_in_user, current_user_subscription: current_user_subscription, email_subscribers: email_subscribers}));
            $("#elog_content").prepend(rendered);
            $('#elog_email_subscriptions').on('hidden.bs.modal', function () { $('#elog_email_subscriptions').remove(); });
            $('#elog_email_subscriptions_subscribe').on("click", function(){ $.getJSON("ws/elog_email_subscribe").done(function(){$('#elog_email_subscriptions').find(".elog_email_subscription_msg").toggleClass("d-none")})});
            $('#elog_email_subscriptions_unsubscribe').on("click", function(){ $.getJSON("ws/elog_email_unsubscribe").done(function(){$('#elog_email_subscriptions').find(".elog_email_subscription_msg").toggleClass("d-none")})});
            $("#elog_email_subscriptions").modal();
        })
    });
    if(logbook_site == "LCLS") {
      $("#elog_daq_ami_issue").removeClass("d-none");
      $("#elog_daq_ami_issue").on("click", function() {
        $.post("../Computing/ws/new_elog_entry", {"log_text": "AMI/DAQ issue in experiment " + experiment_name + " user " + logged_in_user, "log_tags": experiment_name + " AMI_DAQ_Issue"})
        .done(function(){success_message("Logged a AMI/DAQ issue", timeout=1000)})
      })
    }
    $("#elog_search_text").on("input", search_text_input);
}

let attach_websocket = function(trgt) { 
    $(window).scroll(function () {
        if (!_.isNil($("#elog_content").data("spgntr")) && ($(window).scrollTop() >= $(document).height() - $(window).height() - 10)) {
            $("#elog_content").data("spgntr").pageDown();
        }
    });
       
    trgt.querySelector(".lgbk_socketio").addEventListener("elog", function(event){
         if(skip_websocket_elog_messages) { console.log("Skipping elog message from server."); return; }
         var elogData = event.detail.value;
         console.log("Processing elog event for experiment " + experiment_name + " id=" + elogData["_id"]);
         if(_.has(elogData, "sample") && sample_showing_in_UI != null && sample_showing_in_UI != "All Samples" && elogData['sample'] != sample_showing_in_UI) { console.log("Skipping updating elog for different sample " + elogData['sample']); return; }
         processElogEntry(elogData);
         attach_children();
         console.log(elogData);
         if(!_.has(elogData, "root")) {
             $("#elog_content").data("spgntr").addObject(elogData);
         } else {
             console.log("Child row of " + elogData["parent"]);
             let entryinserted = false, newentrydt = moment(elogData['relevance_time']);
             $.each($("#"+elogData["parent"]).find(".edat"), function() {
                 if(!entryinserted) {
                     var existing_entry = $(this).data("entry");
                     var existing_entry_dt = moment(existing_entry['relevance_time']);
                     if (newentrydt.isAfter(existing_entry_dt)) {
                         $(this).before(elogData.render());
                         entryinserted = true;
                     }
                 }
               });
               if(!entryinserted) {
                   console.log("Inserting possible first child entry");
                   $("#"+elogData["parent"]).find(".card-body").append(elogData.render());
                   entryinserted = true;
               }
         }
     });
   
     trgt.querySelector(".lgbk_socketio").addEventListener("runs", function(event){
         if(skip_websocket_elog_messages) { console.log("Skipping run message from server."); return; }
         var runData = event.detail.value;
         console.log("Processing run event for experiment " + experiment_name + " id=" + runData["num"]);
         if(_.has(runData, "sample") && sample_showing_in_UI != null && sample_showing_in_UI != "All Samples" && runData['sample'] != sample_showing_in_UI) {
             $("#elog_content").find("[data-runnum=" + runData["num"]+"]").remove();
             console.log("Skipping updating elog runs for different sample " + runData['sample']); return;
         }
         var newRunEntries = processRunResponse({value: [runData]});
         _.each(newRunEntries, function(r){$("#elog_content").data("spgntr").addObject(r)});
     });
}

export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer lgbk_socketio" id="elog_tab"><div class="mdl_holder"></div><div class="container-fluid text-center" id="elog_content"></div></div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;
    $("#elog_tab").data("entries", id2entry);
    $("#elog_tab").data("refresh", load_elog_function);
    $("#elog_tab").on("lg.refreshOnSampleChange", function() { load_elog_function(); });
  
    load_elog_function();
    attach_toolbar_btns();
    attach_websocket(trgt);
}