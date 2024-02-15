let error_message = function(msg) {
  if(_.isNil(msg)) {
    document.querySelector("#rtbl_new_entry_modal .errormsg").innerHTML = "";
    document.querySelector("#rtbl_new_entry_modal .errormsg").classList.add("d-none");
    return;
  }
  document.querySelector("#rtbl_new_entry_modal .errormsg").innerHTML = msg;
  document.querySelector("#rtbl_new_entry_modal .errormsg").classList.remove("d-none");
}

let anyValidationErrors = function(event) {
  error_message(null);
  if(_.trim(document.querySelector("#rtbl_def_name").value) == "") { error_message("Table name cannot be blank."); return true }
  if(_.trim(document.querySelector("#rtbl_def_desc").value) == "") { error_message("Please enter a brief description."); return true }
  if(!/^([\w-\s]+)$/.test(document.querySelector("#rtbl_def_name").value)) { error_message("We limit the special characters that can be used in table names. Alpha-numeric with underscores and spaces only."); return true }
  if(!/^([0-9]+)$/.test(document.querySelector("#rtbl_sort_index").value)) { error_message("Please enter an integer value for the sort index"); return true }
  let binsz = document.querySelector("#rtbl_def_bin_size").value;
  if(binsz != "" && !/^([0-9.]+)$/.test(binsz)) { error_message("Please enter the size of each bin."); return true }
  let tbltype = document.querySelector("#rtbl_def_table_type").value;
  if(tbltype == "generatedtable" && _.trim(document.querySelector("#rtbl_gentable_patterns").value) == "") {error_message("Please enter a pattern for the attribute names"); return true }
  if(tbltype == "generatedscatter" && _.trim(document.querySelector("#rtbl_gentable_scatter_patterns").value)== "") {error_message("Please enter a pattern for the attribute names"); return true }
  if(!_.includes(["generatedtable", "generatedscatter"], tbltype)) {
    let blankFields = false;
    document.querySelectorAll("#rtbl_def_tbl tbody tr").forEach((tr) => {
      tr.querySelectorAll(".nonblank").forEach((ip) => { 
        if(_.trim(ip.value) == "") {
          blankFields = true;
        }
      })
    })
    if(blankFields) { error_message("At least one column definition should have a complete column definition"); return true }
  }
  return false;
}

export function col_defs_dialog(editTableName) {
    let run_tbl_def_tr = `<tr>
    <td><input name="label" class="nonblank form-control"/></td>
    <td><select name="type" class="rtbl_def_category_select nonblank form-control form-select"><option value="">&nbsp;</option></select></td>
    <td><select name="source" class="rtbl_def_pvname_select nonblank form-control form-select"><option value="">&nbsp;</option></select></td>
    <td>
        <div class="row p-0 m-0"><span class="rtbldef_action col-6"><i class="fa-solid fa-plus fa-lg" aria-hidden="true"></i></span>
        <span class="rtbldef_action col-6"><i class="fa-solid fa-trash fa-lg" aria-hidden="true"></i></span></div>
        <div class="row p-0 m-0"><span class="rtbldef_action col-6"><i class="fa-solid fa-arrow-up fa-lg" aria-hidden="true"></i></span>
        <span class="rtbldef_action col-6"><i class="fa-solid fa-arrow-down fa-lg" aria-hidden="true"></i></span></div>
    </td></tr>`;
  let run_tbl_def_category_selector = `{{#.}}<option value="{{.}}">{{.}}</option>{{/.}}`;
  let run_tbl_def_pvname_selector = `<select name="source" class='rtbl_def_pvname_select nonblank form-control form-select'><option value=''></option>{{#.}}<option value="{{label}}" title="{{param_name}}">{{description}}</option>{{/.}}</select>`;
  Mustache.parse(run_tbl_def_tr);
  Mustache.parse(run_tbl_def_category_selector);
  Mustache.parse(run_tbl_def_pvname_selector);

    $.when($.ajax('../../static/html/tabs/lgbk/rtbl/rtbl_def_modal.html'), $.getJSON('ws/run_table_sources'))
    .done(function(d1, d2) {

      let mdl = $(d1[0]), rtbl_sources = d2[0];
      _.defaults(rtbl_sources.value, {"Editables": []});
      rtbl_sources.value["Editables"].push({"label": "New Editable", "description": "Add a new editable run parameter", "source": "editable_params.", "category": "Editables" });
      $("#rtbl_content").prepend(mdl);
      $("#rtbl_content").data("run_table_sources", rtbl_sources);
      let template_tr = $(Mustache.render(run_tbl_def_tr), {});
      template_tr.find(".rtbl_def_category_select").append(Mustache.render(run_tbl_def_category_selector, _.keys(rtbl_sources.value)));
      template_tr.find(".rtbl_def_category_select").on("change", function(){
        $(this).parent().next().empty().html(Mustache.render(run_tbl_def_pvname_selector, _.sortBy(rtbl_sources.value[$(this).val()]), "description"));
      });
      mdl.find("#rtbl_def_table_type").on("change", function(){
          $("#rtbl_new_entry_modal").find(".ttype").addClass("d-none");
          $("#rtbl_new_entry_modal").find(".ttype_"+$("#rtbl_def_table_type").val()).removeClass("d-none");
      });
      template_tr.find(".fa-plus").parent().on("click", function(e){ e.preventDefault(); $(this).closest("tr").after(template_tr.clone(true)); });
      template_tr.find(".fa-trash").parent().on("click", function(e){ e.preventDefault(); $(this).closest("tr").remove(); });
      template_tr.find(".fa-arrow-up").parent().on("click", function(e){ e.preventDefault(); $(this).closest("tr").prev().before($(this).closest("tr")); });
      template_tr.find(".fa-arrow-down").parent().on("click", function(e){ e.preventDefault(); $(this).closest("tr").next().after($(this).closest("tr")); });
      if (!_.isNil(editTableName)) {
        console.log("Editing table " + editTableName);
        let tblDef = $("#rtbl_tab").data("tblData")[editTableName];
        $("#rtbl_def_id").val(tblDef["_id"]);
        $("#rtbl_def_name").val(tblDef["name"]);
        $("#rtbl_def_desc").val(tblDef["description"]);
        $("#rtbl_def_bin_size").val(_.get(tblDef, "bin_size", ""));
        $("#rtbl_sort_index").val(_.get(tblDef, "sort_index", 100));
        $("#rtbl_gentable_patterns").val(_.get(tblDef, "patterns", ".*"));
        $("#rtbl_gentable_scatter_patterns").val(_.get(tblDef, "patterns", ".*"));
        $("#rtbl_gentable_showvalues").prop("checked", _.get(tblDef, "showvalues", true));
        $("#rtbl_def_table_type").val(_.get(tblDef, "table_type", "table")).trigger("change");
        _.each(_.tail(tblDef["coldefs"]), function(coldef, index){
            let coldefrow = template_tr.clone(true);
            coldefrow.find("[name='label']").val(coldef["label"]);
            let rtbl_src_obj = _.find(_.flatten(_.values(rtbl_sources.value)), function(rdf){return rdf['source'] == coldef["source"]});
            if(!_.isNil(rtbl_src_obj)) {
              coldefrow.find(".rtbl_def_category_select").val(rtbl_src_obj['category']);
              coldefrow.find(".rtbl_def_pvname_select").empty().html(Mustache.render(run_tbl_def_pvname_selector, rtbl_sources.value[rtbl_src_obj['category']])).val(rtbl_src_obj['label']);
            } else {
              console.log("Did not find param description for " + coldef["source"] + " Making one up.");
              rtbl_sources.value["EPICS:Additional parameters"].push({ label: _.replace(coldef["source"], "params.", ""), category: "EPICS:Additional parameters", source: coldef["source"] })
              coldefrow.find(".rtbl_def_category_select").val("EPICS:Additional parameters");
              coldefrow.find(".rtbl_def_pvname_select").empty().html(Mustache.render(run_tbl_def_pvname_selector, rtbl_sources.value["EPICS:Additional parameters"])).val(_.replace(coldef["source"], "params.", ""));
            }
            $("#rtbl_def_tbl tbody").append(coldefrow);
        });
      } else {
        $("#rtbl_def_tbl tbody").append(template_tr.clone(true));
      }
      $("#rtbl_def_post").on("click", function(e){
        if(anyValidationErrors(e)) { return }
        let tbl_def = {
          name: $("#rtbl_def_name").val(),
          description: $("#rtbl_def_desc").val(),
          is_editable: true,
          table_type: $("#rtbl_def_table_type").val(),
          sort_index: _.toInteger($("#rtbl_sort_index").val()),
          coldefs: []
        };
        if(!_.isEmpty($("#rtbl_def_id").val())) { tbl_def["_id"] = $("#rtbl_def_id").val() }
        if(tbl_def['table_type'] == "histogram" && !_.isEmpty($("#rtbl_def_bin_size").val())) { tbl_def['bin_size'] = parseFloat($("#rtbl_def_bin_size").val()); }
        if(tbl_def['table_type'] == "generatedtable") { 
          tbl_def['patterns'] = _.trim($("#rtbl_gentable_patterns").val()); 
          tbl_def['showvalues'] = $("#rtbl_gentable_showvalues").is(':checked'); 
        }
        if(tbl_def['table_type'] == "generatedscatter") { 
          tbl_def['patterns'] = _.trim($("#rtbl_gentable_scatter_patterns").val()); 
        }
        if(!_.includes(["generatedtable", "generatedscatter"], tbl_def['table_type'])) {
            $("#rtbl_def_tbl tbody tr").each(function(index, defnrow){
              let colname = $(this).find("[name='label']").val();
              let type = $(this).find("[name='type']").val();
              let srclbl = $(this).find("[name='source']").val();
              console.log("Looking for source for " + srclbl);
              let source = (srclbl == "New Editable") ? "editable_params." + colname + ".value" : _.find($("#rtbl_content").data("run_table_sources").value[type], function(o){ return o['label'] == srclbl; })['source'];
              tbl_def.coldefs.push({
                label: colname,
                type: type,
                source: source,
                is_editable: ((type == "Editables") || (_.startsWith(source, "params.Calibrations/"))),
                position: index
              })
            })
        }
            $.getJSON({
                url: 'ws/create_update_user_run_table_def',
                data: JSON.stringify(tbl_def),
            type: "POST",
                contentType: 'application/json'
              })
              .done(function(data, textStatus, jqXHR) {
                  if(data.success) { console.log("Successfully updated user run table definition"); sessionStorage['runtable_active_tab'] = $("#rtbl_def_name").val(); $("#rtbl_new_entry_modal").modal("hide"); window.location.reload(true); } else { error_message(data.errormsg); }
              })
              .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); error_message("Server side exception updating user run table definition " + jqXHR.responseText); })
      });
      $("#rtbl_new_entry_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); });
      $("#rtbl_new_entry_modal").modal("show");
    });
 }