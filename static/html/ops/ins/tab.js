var instmpl = `{{#value}}<tr>
<td class="instrument_lbl" style="background:{{color}}; color:{{#color}}white{{/color}}{{^color}}black{{/color}}; " >{{ _id }}</td>
<td>{{ description }}</td>
<td>{{ params.num_stations}}</td>
<td> <span class="editinsbtn"><i class="fas fa-edit fa-lg"></i></span></td>
</tr>{{/value}}`;
Mustache.parse(instmpl);


var show_validation_message = function(message) {
  $("#ins_mdl_holder").find(".validation_message").html(message);
  $("#ins_mdl_holder").find(".validation_modal").modal("show");
}
var editcreatefn = function(instr_obj) {
$.ajax ("../../static/html/ms/insedit.html")
.done(function(tmpl){
  Mustache.parse(tmpl);
  instr_obj.paramkvs = _.map(instr_obj['params'], function(value, key) { return { key: key, value: value };});
  var rendered = $(Mustache.render(tmpl, instr_obj));
  rendered.find(".fa-plus").parent().on("click", function(){ $(this).closest("tr").after($(this).closest("tr").clone(true).find("input").val("").end()); });
  rendered.find(".fa-trash").parent().on("click", function(){ $(this).closest("tr").remove(); });
  if(_.has(instr_obj, '_id')) { rendered.find(".register_btn").text("Update");}
  rendered.find(".register_btn").on("click", function(e) {
    e.preventDefault();
    var formObj = $("#ins_mdl_holder").find("form");
    var validations = [
        [function() { return $.trim(formObj.find(".instrument_name").val()) == ""; }, "Instrument name cannot be blank."],
        [function() { return $.trim(formObj.find(".description").val()) == ""; }, "Please enter a description for the instrument."],
        [function() { return formObj.find("tbody tr").map(function() { return $(this).find("input.key").val() == "" ^ $(this).find("input.value").val() == ""; }).toArray().reduce(function(a, b) { return a + b; }, 0); }, "Every param that has a name must have a value and vice versa."]
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
    var instrument_name = $.trim(formObj.find(".instrument_name").val());
    var original_instrument_name = $.trim(formObj.find(".instrument_name_original").val());
    var ins_params = {};
    formObj.find("tbody tr").map(function() {  var key = $(this).find("input.key").val(), val = $(this).find("input.value").val(); if(key != "" && val != "") { ins_params[key] = val; }});

    var updating_existing_instrument = (original_instrument_name == instrument_name);
    var registration_doc = {
        "_id" : instrument_name,
        "description" : $.trim(formObj.find(".description").val()),
        "color": $.trim(formObj.find(".instrument_color").val()),
        "params": ins_params
    };

    $.ajax({
      type: "POST",
      contentType: "application/json; charset=utf-8",
      url: create_update_instrument + "?instrument_name=" + encodeURIComponent(instrument_name) + "&create=" + (updating_existing_instrument ? false : true),
      data: JSON.stringify(registration_doc),
      dataType: "json"
    })
    .done(function(data, textStatus, jqXHR) {
      if(data.success) {
          console.log("Successfully processed instrument " + instrument_name);
          $("#ins_mdl_holder").find(".edit_modal").modal("hide");
          sessionStorage.setItem("ops_active_tab", "instruments");
          window.location.reload(true);
      } else {
        show_validation_message("Server side: " + data.errormsg);
      }
    })
    .fail( function(jqXHR, textStatus, errorThrown) { show_validation_message("Server side: " + _.get(jqXHR, "responseText", textStatus))})
  });
  $("#ins_mdl_holder").append(rendered);
  $("#ins_mdl_holder").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#ins_mdl_holder").empty(); });
  $("#ins_mdl_holder").find(".edit_modal").modal("show");
});
}


export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="ops_instruments_tab">
  <div class="row">
      <div id="ins_mdl_holder"></div>
      <div class="table-responsive">
          <table class="table table-condensed table-striped table-bordered" id="instrumentstbl">
              <thead><tr><th>Name</th><th>Description</th><th>Number of Stations</th><th>Edit</th></tr></thead>
              <tbody></tbody>
          </table>
      </div>
  </div>
  </div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;

  $("#ops_instruments_tab").data("editcreatefn", editcreatefn);

  $.getJSON(instruments_url)
  .done(function(instruments){
    var rendered = $(Mustache.render(instmpl, instruments));
    rendered.find(".editinsbtn").on("click", function(e){
      e.preventDefault();
      console.log("Editing instrument " + insname);
      var insname = $(this).closest("tr").find("td").first().text();
      var instr_obj = _.find(instruments.value, function(instr){ return instr._id == insname; });
      editcreatefn(instr_obj);
    });
    $("#instrumentstbl tbody").append(rendered);
  });

  var tab_toolbar = `<span id="new_instrument" title="Add a new instrument"><i class="fas fa-plus fa-lg"></i></span>`;
  var toolbar_rendered = $(tab_toolbar);
  $("#toolbar_for_tab").append(toolbar_rendered);
  $("#new_instrument").on("click", function(){ $("#ops_instruments_tab").data("editcreatefn")({})});
}
