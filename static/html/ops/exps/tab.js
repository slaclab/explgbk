import { lgbk_create_edit_exp } from "../../mdls/exp/reg.js";

// Use server side pagination support. The following var's contains the data structures for this support.
var curr_exp_ids = [], all_exp_ids, pg_id_to_details = {}, showing_search_results = false;
var exper_template = `{{#value}}<tr data-expid="{{_id}}">
<td> <a target="_blank" href="../{{_id}}/info">{{ name }}</a> </td>
<td style="background:{{background}}; color:{{color}}; " > {{ instrument }} </td>
<td> {{#FormatDate}}{{start_time }}{{/FormatDate}} </td>
<td> {{#FormatDate}}{{end_time}}{{/FormatDate}} </td>
<td> {{ contact_info }} </td>
<td> {{ leader_account }} </td>
<td> {{ description }} </td>
<td class="ops_exp_icons"><span class="exp_edit" title="Edit"><i class="fa-solid fa-edit fa-lg"></i></span>
  <span class="exp_clone" title="Clone"><i class="fa-solid fa-clone fa-lg"></i></span>
  <span class="exp_rename" title="Rename"><i class="fa-solid fa-suitcase fa-lg"></i></span>
  {{#is_locked}}<span class="lock_unlock" title="Unlock"><i class="fa-solid fa-unlock fa-lg"></i></span>{{/is_locked}}{{^is_locked}}<span class="lock_unlock" title="Lock"><i class="fa-solid fa-lock fa-lg"></i></span>{{/is_locked}}
  {{#privileges.experiment_delete}}<span class="exper_migrate_attachments" title="Migrate attachments to a local store - this is usually a step in archival of the experiment"><i class="fa-solid fa-coins fa-lg"></i></span><span class="exper_delete" title="Delete experiment"><i class="fa-solid fa-trash fa-lg"></i></span>{{/privileges.experiment_delete}}</td>
</tr>{{/value}}`;
Mustache.parse(exper_template);


var rename_exp = function() {
  var src_experiment_name = $(this).closest("tr").find("td").first().find("a").text()
  console.log("Renaming experiment " + src_experiment_name);
  $.ajax ("../../static/html/ms/exprename.html")
  .done(function( tmpl ) {
    Mustache.parse(tmpl);
    var rendered = $(Mustache.render(tmpl, {src_experiment_name: src_experiment_name}));
    rendered.find(".rename_btn").on("click", function(e) {
      e.preventDefault();
      var formObj = $("#exp_mdl_holder").find("form");
      var validations = [
          [function() { return $.trim(formObj.find(".experiment_name").val()) == ""; }, "Experiment name cannot be blank."],
          [function() { return $.trim(formObj.find(".experiment_name").val()) == formObj.find(".src_experiment_name").val(); }, "Experiment name cannot be the same as the original."],
        ];
      // Various validations
      var v_failed = false;
      _.each(validations, function(validation, i) {
        // console.log("Trying validation " + i + "" + validation[1]);
        if(validation[0]()) {
            show_validation_message(validation[1]);
            v_failed = true;
            return false;
        }
      });
      if (v_failed) { e.preventDefault(); return; }
      var experiment_name = $.trim(formObj.find(".experiment_name").val());
      var registration_doc = {};

      $.ajax({
        type: "POST",
        contentType: "application/json; charset=utf-8",
        url: rename_experiment_url + "?experiment_name=" + encodeURIComponent(src_experiment_name) + "&new_experiment_name=" + encodeURIComponent(experiment_name),
        dataType: "json"
      })
      .done(function(data, textStatus, jqXHR) {
        if(data.success) {
            console.log("Successfully renamed experiment " + src_experiment_name + " to " + experiment_name);
            $("#exp_mdl_holder").find(".edit_modal").modal("hide");
            sessionStorage.setItem("ops_active_tab", "experiments");
            sessionStorage.setItem("scroll_to_exp_id", _.replace(experiment_name, " ", "_"));
            window.location.reload(true);
        } else {
          show_validation_message("Server failure: " + data.errormsg);
        }
      })
      .fail( function(jqXHR, textStatus, errorThrown) { show_validation_message("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
    });
   $("#exp_mdl_holder").append(rendered);
   $("#exp_mdl_holder").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#exp_mdl_holder").empty(); });
   $("#exp_mdl_holder").find(".edit_modal").modal("show");
  });
}

var lock_unlock_experiment = function() {
  var experiment_name = $(this).closest("tr").find("td").first().find("a").text()
  console.log("Locking/unlocking experiment " + experiment_name);
  $.ajax({
    type: "POST",
    url: lock_unlock_experiment_url + "?experiment_name=" + encodeURIComponent(experiment_name),
    dataType: "json"
  })
  .done(function(data, textStatus, jqXHR) {
    if(data.success) {
        console.log("Successfully locked experiment " + experiment_name);
        sessionStorage.setItem("ops_active_tab", "experiments");
        sessionStorage.setItem("scroll_to_exp_id", _.replace(experiment_name, " ", "_"));
        window.location.reload(true);
    } else {
      show_validation_message("Server failure: " + data.errormsg);
    }
  })
  .fail( function(jqXHR, textStatus, errorThrown) { show_validation_message("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
}

var migrate_attachments = function() {
  var experiment_name = $(this).closest("tr").find("td").first().find("a").text()
  console.log("Migrating attachments for experiment " + experiment_name);
  $.getJSON({
    type: "POST",
    url: _.replace(experiment_name, " ", "_") + "/migrate_attachments",
    dataType: "json"
  })
  .done(function(data, textStatus, jqXHR) {
    if(data.success) {
        alert("Successfully migrated attachments for experiment " + experiment_name);
    } else {
      alert("Server failure: " + data.errormsg);
    }
  })
  .fail( function(jqXHR, textStatus, errorThrown) { alert("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
}

var delete_experiment = function() {
  var experiment_name = $(this).closest("tr").find("td").first().find("a").text()
  console.log("Deleting experiment " + experiment_name);
  $.ajax ("../../static/html/ms/generic_yes_no.html")
  .done(function( tmpl ) {
    Mustache.parse(tmpl);
    var rendered = $(Mustache.render(tmpl, {"title": "Delete experiment", "message": "Are you sure you want to delete experiment " + experiment_name + "?"}));
    rendered.find(".yesbutton").on("click", function(e) {
      $.ajax({
        type: "DELETE",
        url: "../" + experiment_name + "/",
        dataType: "json"
      })
      .done(function(data, textStatus, jqXHR) {
        if(data.success) {
            console.log("Successfully deleted experiment " + experiment_name);
            $("#exp_mdl_holder").find(".modal").modal("hide");
            window.location.reload(true);
        } else {
          alert("Server failure: " + data.errormsg);
        }
      })
      .fail( function(jqXHR, textStatus, errorThrown) { alert("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
    });
   $("#exp_mdl_holder").append(rendered);
   $("#exp_mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#exp_mdl_holder").empty(); });
   $("#exp_mdl_holder").find(".modal").modal("show");
  });
}

var show_validation_message = function(message) {
  $("#exp_mdl_holder").find(".validation_message").html(message);
  $("#exp_mdl_holder").find(".validation_modal").modal("show");
}

var edit_exp_btn_action = function(){
  var expName = $(this).closest("tr").find("td").first().find("a").text()
  console.log("Editing experiment " + expName);
  $.getJSON("../../lgbk/" + expName + "/ws/info")
  .done(function(info){
      lgbk_create_edit_exp(info["value"]);
  })
};

var render_current_exps = function(use_append) {
  let displayed_experiment_ids = $("#exp_searchresults tbody tr").map(function(x) { return $(this).attr("data-expid") }).get();
  let exps_to_display = _.difference(curr_exp_ids, displayed_experiment_ids);
  if(_.isEmpty(exps_to_display)) { return; }
  if(_.isEmpty(displayed_experiment_ids)) { use_append = true }
  let exps_missing_info = _.difference(curr_exp_ids, _.keys(pg_id_to_details)), ins2colors = $("#register_edit_exp_tab").data("ins2colors");
  console.log("Getting details using POST for these experiments");
  console.log(exps_missing_info);
  $.post({url: "../../lgbk/ws/get_experiment_infos", data: JSON.stringify(exps_missing_info), contentType: "application/json; charset=utf-8", dataType: "json"})
  .done(function(d0){
    _.each(d0.value, function(e){ pg_id_to_details[e["_id"]] = e; e["background"] = ins2colors[e["instrument"]]["bg"]; e["color"] = ins2colors[e["instrument"]]["fg"]; });
    let expdata = { value: _.reject(_.map(exps_to_display, (x) => { return pg_id_to_details[x] }), _.isNil) , privileges: privileges, FormatDate: elog_formatdate };
    var rendered = $(Mustache.render(exper_template, expdata));
    rendered.find(".ops_exp_icons .exp_edit").on("click", edit_exp_btn_action);
    rendered.find(".ops_exp_icons .exp_clone").on("click", function(){
        async function loadCloneModal(experiment_name) {
          const { clone_experiment } = await import(lgbkabspath("/static/html/mdls/exp/clone.js"));
          clone_experiment(experiment_name, (cloned_experiment_name) => {
            sessionStorage.setItem("ops_active_tab", "experiments");
            sessionStorage.setItem("scroll_to_exp_id", _.replace(cloned_experiment_name, " ", "_"));
            window.location.reload(true);
          });
        }  
      let src_experiment_name = $(this).closest("tr").find("td").first().find("a").text()
      loadCloneModal(src_experiment_name);
    });
    rendered.find(".ops_exp_icons .exp_rename").on("click", rename_exp);
    rendered.find(".ops_exp_icons .lock_unlock").on("click", lock_unlock_experiment);
    rendered.find(".ops_exp_icons .exper_migrate_attachments").on("click", migrate_attachments);
    rendered.find(".ops_exp_icons .exper_delete").on("click", delete_experiment);
    if(use_append) { $("#exp_searchresults tbody").append(rendered); } else { $("#exp_searchresults tbody").prepend(rendered); }
  })
}

let search_function = function() {
  if($("#ops_exp_searchtext").val().length > 2) {
    $.getJSON({ url: "../ws/ops_search_exp_infos", data: { search_text: $("#ops_exp_searchtext").val(), sort: JSON.stringify([[$("#register_edit_exp_tab").data("cur_sort_attr"), $("#register_edit_exp_tab").data("cur_sort_desc") ? -1 : 1 ]]) } })
    .done(function(d0){
      $("#exp_searchresults tbody").empty();
      showing_search_results = true;
      curr_exp_ids = d0.value;
      render_current_exps(true);
    })
  } else {
    if(showing_search_results) {
      showing_search_results = false;
      $("#exp_searchresults tbody").empty();
      curr_exp_ids = _.slice(all_exp_ids, 0, 100);
      render_current_exps(true);
    }
  }
}

let scroll_function = function (){
  if(showing_search_results) return;
  if ($(window).scrollTop() >= $(document).height() - $(window).height() - 10) {
    let next_page_exp_names = _.union(curr_exp_ids, _.slice(all_exp_ids, curr_exp_ids.length, curr_exp_ids.length+100));
    curr_exp_ids = next_page_exp_names
    render_current_exps(true);
  }
}

let sort_function = function() {
  var curr_attr = $("#register_edit_exp_tab").data("cur_sort_attr");
  var sel_attr = $(this).attr("data-sort-attr");
  if(curr_attr == sel_attr) {
      $("#register_edit_exp_tab").data("cur_sort_desc", !$("#register_edit_exp_tab").data("cur_sort_desc"));
      $(this).closest("th").find(".sric").remove();
  } else {
      $("#register_edit_exp_tab").data("cur_sort_attr", sel_attr)
      $("#register_edit_exp_tab").data("cur_sort_desc", true);
      $(this).closest("thead").find(".sric").remove();
  }
  $(this).closest("th").append($("#register_edit_exp_tab").data("cur_sort_desc") ? $('<i class="fa-solid fa-sort-down sric"></i>') : $('<i class="fa-solid fa-sort-up sric"></i>'))
  $.getJSON({ url: "../ws/sorted_experiment_ids", data: {sort: JSON.stringify([[$("#register_edit_exp_tab").data("cur_sort_attr"), $("#register_edit_exp_tab").data("cur_sort_desc") ? -1 : 1 ]])} })
  .done(function(d0){
    $("#exp_searchresults tbody").empty();
    all_exp_ids = d0.value;
    curr_exp_ids = _.slice(all_exp_ids, 0, 100);
    render_current_exps(true);
  });
}

export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer lgbk_socketio" id="register_edit_exp_tab">
  <div id="exp_mdl_holder"></div>
  <div class="row">
      <div class="table-responsive">
          <table class="table table-condensed table-striped table-bordered" id="exp_searchresults">
              <thead><tr>
                  <th data-sort-attr="name">Name</th>
                  <th data-sort-attr="instrument">Instrument</th>
                  <th data-sort-attr="start_time">Experiment start<i class="fa-solid fa-sort-up sric"></i></th>
                  <th data-sort-attr="end_time">Experiment end</th>
                  <th data-sort-attr="contact_info">PI</th>
                  <th data-sort-attr="leader_account">Leader Account</th>
                  <th data-sort-attr="description">Description</th>
                  <th>Edit</th>
              </tr></thead>
              <tbody></tbody>
          </table>
      </div>
  </div>
  </div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;
  
  $("#register_edit_exp_tab").data("cur_sort_attr", "start_time");
  $("#register_edit_exp_tab").data("cur_sort_desc", false);
  
  $(window).scroll(scroll_function);
  $("#register_edit_exp_tab").data("search_function", search_function); // Register the search function.
  
  $.when($.getJSON({ url: "../ws/sorted_experiment_ids" }), $.getJSON({ url: instruments_url }))
  .done(function(d0, d1) {
    let instruments = _.keyBy(d1[0].value, "_id");
    all_exp_ids = d0[0].value;
    curr_exp_ids = _.slice(all_exp_ids, 0, 100);
    $("#register_edit_exp_tab").data("ins2colors", _.fromPairs(_.map(instruments, (ii) => { return [ ii["_id"], { "bg": _.get(ii, "color", "inherit"), "fg": _.has(ii, "color") ? "white" : "black" }]})));
    render_current_exps(true);

    if(sessionStorage.getItem("scroll_to_exp_id") != null) {
        console.log("Scrolling to " + sessionStorage.getItem("scroll_to_exp_id"));
        var row = $('#exp_searchresults').find('tr[data-expid="' + sessionStorage.getItem("scroll_to_exp_id") + '"]');
        if(row.length > 0) { row[0].scrollIntoView(); }
        sessionStorage.removeItem("scroll_to_exp_id");
    }
  });

  trgt.querySelector(".lgbk_socketio").addEventListener("experiments", function(event){
    let experiment = event.detail;
    console.log("Processing experiment message for " + experiment.value["name"]);
    if(_.get(experiment, "CRUD", "") == "Create") {
      $.getJSON("../" + experiment.value["name"] + "/ws/info")
      .done(function(d0){
        console.log(d0);
        curr_exp_ids.unshift(d0.value["_id"]);
        render_current_exps(false);
        if(!_.isNil(window.scrollToExperiment) && window.scrollToExperiment) {
          var row = $('#exp_searchresults').find('tr[data-expid="' + experiment.value["name"] + '"]');
          if(row.length > 0) { row[0].scrollIntoView(); }
          window.scrollToExperiment = false;
        }
      })
    }
  });
  
  $("#exp_searchresults th[data-sort-attr]").on("click", sort_function);

  var tab_toolbar = `<input type="text" placeholder="Search" id="ops_exp_searchtext">
  <span id="register_experiment" title="Register New Experiment"><i class="fa-solid fa-plus fa-lg"></i></span>`;
  var toolbar_rendered = $(tab_toolbar);
  $("#toolbar_for_tab").append(toolbar_rendered);
  $("#ops_exp_searchtext").on("input", function(){ $("#register_edit_exp_tab").data("search_function")() });
  $("#register_experiment").on("click", function(){
    lgbk_create_edit_exp({ contact_info: "", start_time : moment(), end_time : moment().add(2, 'days')});
  });
}