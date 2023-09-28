let create_edit_wf_def = function(wf_id) {
  $.when($.ajax("../../static/html/tabs/lcls/wf_def_edit.html"), $.getJSON('ws/workflow_definitions'), $.getJSON('ws/dm_locations'), $.getJSON('ws/workflow_triggers'))
  .done(function(d0, d1, d2, d3){
      let wf_def = ( _.isNil(wf_id) ? {} : _.find(d1[0].value, ["_id", wf_id])), lc = _.set(wf_def, "locations", _.map(_.filter(d2[0].value, "jid_prefix"), "name")), lt = _.set(wf_def, "triggers", d3[0].value), rendered = $(Mustache.render(d0[0], wf_def));
      rendered.find(".wf_def_trigger").on("change", function(){ if($(this).val() == "RUN_PARAM_IS_VALUE"){ rendered.find(".run_tbl_trigger_params").removeClass("d-none")} else { rendered.find(".run_tbl_trigger_params").addClass("d-none")}})
      rendered.find(".wf_def_trigger").val(_.get(wf_def, "trigger", _.first(d3[0].value)["value"]));
      rendered.find(".wf_def_location").val(_.get(wf_def, "location", _.first(d2[0].value)["name"]));
      if(_.get(wf_def, "trigger") == "RUN_PARAM_IS_VALUE"){ rendered.find(".run_tbl_trigger_params").removeClass("d-none")}
      $("#lcls_wf_defs_tab").find("#mdl_holder").empty().append(rendered);
      $("#lcls_wf_defs_tab").find("#mdl_holder").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#lcls_wf_defs_tab").find("#mdl_holder").empty(); });
      $("#lcls_wf_defs_tab").find("#mdl_holder").find(".edit_modal").modal("show");
      rendered.find(".submit_btn").on("click", function(e) {
        e.preventDefault();
        let formObj = $(this).closest("form"), modalObj = $(this).closest(".modal");
        var show_validation_message = function(message) { error_message(message) }
        var validations = [
            [function() { return $.trim(formObj.find(".wf_def_name").val()) == ""; }, "Please enter a name."],
            [function() { return $.trim(formObj.find(".wf_def_executable").val()) == ""; }, "Please enter the path to the script you want to trigger."],
            [function() { return $.trim(formObj.find(".wf_def_trigger").val()) == "RUN_PARAM_IS_VALUE" && $.trim(formObj.find(".wf_run_param_name").val()) == ""; }, "Please enter a valid run parameter name."],
            [function() { return $.trim(formObj.find(".wf_def_trigger").val()) == "RUN_PARAM_IS_VALUE" && $.trim(formObj.find(".wf_run_param_value").val()) == ""; }, "Please enter a valid run parameter value."]
          ];
        // Various validations
        var v_failed = false;
        _.each(validations, function(validation, i) {
          console.log("Trying validation " + i + "" + validation[1]);
          if(validation[0]()) {
              show_validation_message(validation[1]);
              v_failed = true;
              return false;
          }
        });
        if (v_failed) { e.preventDefault(); return; }
        var wf_def_name = $.trim(formObj.find(".wf_def_name").val());
        var wf_def_id_original = $.trim(formObj.find(".wf_def_id").val());
        var new_wf_def_doc = {
          name: wf_def_name,
          executable: $.trim(formObj.find(".wf_def_executable").val()),
          trigger: $.trim(formObj.find(".wf_def_trigger").val()),
          location: $.trim(formObj.find(".wf_def_location").val()),
          parameters: $.trim(formObj.find(".wf_def_parameters").val())
        };
        if( !_.isNil(wf_def_id_original) && $.trim(wf_def_id_original).length > 1 ) { new_wf_def_doc["_id"] = wf_def_id_original }
        if($.trim(formObj.find(".wf_def_trigger").val()) == "RUN_PARAM_IS_VALUE") { new_wf_def_doc["run_param_name"] = $.trim(formObj.find(".wf_run_param_name").val()); new_wf_def_doc["run_param_value"] = $.trim(formObj.find(".wf_run_param_value").val()); }
        console.log(new_wf_def_doc);
        $.ajax({
          type: "POST",
          contentType: "application/json; charset=utf-8",
          url: "ws/create_update_workflow_def",
          data: JSON.stringify(new_wf_def_doc),
          dataType: "json"
        })
        .done(function(data, textStatus, jqXHR) {
          if(data.success) {
              console.log("Successfully create workflow definition " + wf_def_name);
              $("#lcls_wf_defs_tab").find("#mdl_holder").find(".edit_modal").modal("hide");
              window.location.reload(true);
          } else {
            alert("Server side exception processing workflow definition " + data.errormsg);
          }
        })
        .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure processing workflow definition " + textStatus); })
    })
  })
}



export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer alwaysreload" id="lcls_wf_defs_tab">
    <div id="mdl_holder"></div>
    <div class="container-fluid text-center" id="wf_defs_content">
      <div class="table-responsive">
        <table id="lcls_wf_defs_tbl" class="table table-condensed table-striped table-bordered wf_defs_tbl">
          <thead><tr><th>Name</th><th>Executable</th><th>Parameters</th><th>Location</th><th>Trigger</th><th>As user</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;


  var ws_defs_tmpl = `{{#value}}<tr data-id="{{_id}}"><td>{{name}}</td><td>{{executable}}</td><td>{{parameters}}</td><td>{{location}}</td><td>{{trigger}}{{#run_param_name}}<div class="wf_run_params">{{run_param_name}} == {{run_param_value}}{{/run_param_name}}</div></td><td>{{run_as_user}}</td><td><span title="Edit definition"><i class="fas fa-edit listview-action"></i></span><span title="Delete definition"><i class="fas fa-trash listview-action"></i></span></td></tr>{{/value}}`;
  Mustache.parse(ws_defs_tmpl);
  $.getJSON('ws/workflow_definitions').done(function(d){
      let rendered = $(Mustache.render(ws_defs_tmpl, d));
      rendered.find(".fa-edit").parent().on("click", function(){
          let wf_id = $(this).closest("tr").attr("data-id");
          create_edit_wf_def(wf_id);
      })
      rendered.find(".fa-trash").parent().on("click", function(){
          let wf_id = $(this).closest("tr").attr("data-id");
          $.getJSON({url: "ws/workflow_definitions/"+encodeURIComponent(wf_id), method: "DELETE" })
          .done(function(data){ if(data.success){ window.location.reload(true) } else { error_message(data.errormsg)}})
          .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); error_message("Server side exception deleting workflow definition " + jqXHR.responseText); })
      })
      $("#lcls_wf_defs_tbl tbody").empty().append(rendered);
  })
 

  var tab_toolbar = `<span id="new_wf_def"><i class="fas fa-plus fa-lg"></i></span>`;
  var toolbar_rendered = $(tab_toolbar);
  $("#toolbar_for_tab").append(toolbar_rendered);
  $("#new_wf_def").on("click", function(e){ create_edit_wf_def()});



}
