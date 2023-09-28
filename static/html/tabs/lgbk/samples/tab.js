
const SAMPLE_MODAL = lgbkabspath("/static/html/mdls/samples/modal.js");
const INFO_MODAL = lgbkabspath("/static/html/mdls/samples/info.js");
const ALL_SAMPLES_URL = lgbkabspath(`/lgbk/${experiment_name}/ws/samples/`);
  
async function loadAndShowSampleModal(sampleid) {
    const { modalshow } = await import(SAMPLE_MODAL);
    modalshow(sampleid, ALL_SAMPLES_URL, () => { refreshTab() });
}

async function loadAndShowInfoModal(sampleid) { 
  const { modalshow } = await import(INFO_MODAL);
  modalshow(sampleid, ALL_SAMPLES_URL, () => { });
}

var edit_sample = function(sample_obj) {
  loadAndShowSampleModal(_.get(sample_obj, "_id", null));
}

let display_sample = function(sample_obj) {
  loadAndShowInfoModal(sample_obj["_id"]);
}


  var clone_sample = function(existing_sample_name) {
      $.ajax("../../static/html/ms/gen_clone.html")
      .done(function(tmpl){
          Mustache.parse(tmpl);
          var rendered = $(Mustache.render(tmpl, {object_type: "sample", title: "Clone " + existing_sample_name, existing_object_name: existing_sample_name, btnlbl: "Clone"}));
          rendered.find("#obj_clone_btn").on("click", function(e){
              console.log("Cloning");
              e.preventDefault();
              var formObj = $("#glbl_modals_go_here").find("form");
              var validations = [
                  [function() { return $.trim(formObj.find(".new_object_name").val()) == ""; }, "Sample name cannot be blank."],
                  [function() { return !/^[\w/_-]+$/.test($.trim(formObj.find(".new_object_name").val())); }, "Please restrict sample names to alphanumeric characters, dashes, slashes and underscores."],
                  [function() { return _.find($("#samples_tab").data("samples").value, function(shf){return shf.name == $.trim(formObj.find(".new_object_name").val())}) != undefined }, "The sample name already exists."]
              ];
              // Various validations
              var v_failed = false;
              _.each(validations, function(validation, i) {
                  console.log("Trying validation " + i + "" + validation[1]);
                  if(validation[0]()) {
                      error_message(validation[1]);
                      v_failed = true;
                      return false;
                  }
              });
              if (v_failed) { e.preventDefault(); return; }
              var sample_name = $.trim(formObj.find(".new_object_name").val());
              $.getJSON("ws/clone_sample"+ "?existing_sample_name=" + encodeURIComponent(existing_sample_name) + "&new_sample_name=" + encodeURIComponent($.trim(formObj.find(".new_object_name").val())))
              .done(function(data, textStatus, jqXHR) {
                  if(data.success) {
                      console.log("Successfully cloned sample " + sample_name);
                      $("#glbl_modals_go_here").find(".edit_modal").modal("hide");
                      window.location.reload(true);
                  } else {
                      alert("Server side exception cloning sample " + data.errormsg);
                  }
              })
              .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure cloning sample " + textStatus); })
          });
          $("#glbl_modals_go_here").empty().append(rendered);
          $("#glbl_modals_go_here").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#glbl_modals_go_here").empty(); });
          $("#glbl_modals_go_here").find(".edit_modal").modal("show");
      });
  }

  var delete_sample = function(sample_obj) {
    $.when($.getJSON("ws/runs", {"sampleName": sample_obj["name"], "includeParams": "false"}), $.ajax("../../static/html/ms/generic_msg.html"))
    .done(function(d0, d1) {
        let show_error = function(title, message) {
            let rendered = Mustache.render(msg_tmpl, {"title": title, "message": message});
            $("#glbl_modals_go_here").empty().append(rendered);
            $("#glbl_modals_go_here").find(".modal").modal("show");
        }
        let sampruns = d0[0], msg_tmpl = d1[0]; Mustache.parse(msg_tmpl);
        if(sampruns["value"].length > 0) {
            show_error("Sample " + sample_obj["name"], "Cannot delete sample " + sample_obj["name"] + " as there are " + sampruns["value"].length + " run(s) associated with it.");
            return;
        } else {
            console.log("Deleting sample " + sample_obj["name"]);
            $.getJSON({url: "ws/samples/"+encodeURIComponent(sample_obj["name"]), method: "DELETE" })
            .done(function(data){ if(data.success){ window.location.reload(true) } else { show_error("Error deleting sample", data.errormsg)}})
            .fail(function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); alert("Server side exception deleting sample " + jqXHR.responseText); })
        }
    })
  }

  let loadSampleData = function() {
  $("#samples_tab").data("edit_sample", edit_sample);

  var sample_tr_tmpl = `{{#value}}<tr {{#current}}class="active_sample"{{/current}}><td><a class="smplnm" href="#">{{ name }}</a></td><td>{{ description }}</td><td>
      <span title="Display sample details"><i class="fas fa-info-circle listview-action"></i></span>
      <span title="Edit sample details" class="hide_when_locked"><i class="fas fa-edit listview-action"></i></span>
      <span title="Clone sample" class="hide_when_locked"><i class="fas fa-clone listview-action"></i></span>
      {{^current}}<span title="Make this sample the current sample" class="hide_when_locked"><span><i class="fas fa-play listview-action"></i></span></span>{{/current}}
      {{#current}}<span title="Stop this sample and set the current sample to null" class="hide_when_locked"><span><i class="fas fa-stop listview-action"></i></span></span>{{/current}}
      <span title="Delete sample; a sample can be deleted only if there are no runs associated with it."><i class="fas fa-trash listview-action"></i></span></td></tr>{{/value}}`;
  Mustache.parse(sample_tr_tmpl);
  $.getJSON("ws/samples")
  .done(function(data){
    data.FormatDate = elog_formatdatetime;
    $("#samples_tab").data("samples", data);
    var rendered = $(Mustache.render(sample_tr_tmpl, data));
    if(is_locked){ rendered.find(".hide_when_locked").addClass("d-none") }
    rendered.find(".fa-play").parent().on("click", function(){
      var sample_name = $(this).closest("tr").find("td").first().text();
      $.getJSON({url: "ws/make_sample_current?sample_name="+encodeURIComponent(sample_name), method: "POST" })
      .done(function(data, textStatus, jqXHR) {
        if(data.success) {
            console.log("Successfully played sample " + sample_name);
            window.location.reload(true);
        } else {
          alert("Server side exception playing sample " + sample_name + "\n" + data.errormsg);
        }
      })
      .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure closing sample " + textStatus); })
    });
    rendered.find(".fa-stop").parent().on("click", function(){
      var sample_name = $(this).closest("tr").find("td").first().text();
      $.getJSON({url: "ws/stop_current_sample?sample_name="+encodeURIComponent(sample_name), method: "POST" })
      .done(function(data, textStatus, jqXHR) {
        if(data.success) {
            console.log("Successfully stopped sample " + sample_name);
            window.location.reload(true);
        } else {
          alert("Server side exception stopping sample " + sample_name + "\n" + data.errormsg);
        }
      })
      .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure closing sample " + textStatus); })
    })
    rendered.find(".fa-edit").parent().on("click", function(){
      var sample_name = $(this).closest("tr").find("td").first().text();
      $.getJSON("ws/samples/"+sample_name).done(function(data){edit_sample(data["value"]);})
    });
    rendered.find(".fa-clone").parent().on("click", function(){
        var existing_sample_name = $(this).closest("tr").find("td").first().text();
        clone_sample(existing_sample_name);
    });
    let smplinfofn = function(dis) {
        var sample_name = dis.closest("tr").find("td").first().text();
        $.getJSON("ws/samples/"+sample_name).done(function(data){display_sample(data["value"]);})
    }
    rendered.find(".fa-info-circle").parent().on("click", function(){ smplinfofn($(this)) });
    rendered.find(".smplnm").on("click", function(){ smplinfofn($(this)) });
    rendered.find(".fa-trash").parent().on("click", function(){
      var sample_name = $(this).closest("tr").find("td").first().text();
      $.getJSON("ws/samples/"+sample_name).done(function(data){delete_sample(data["value"]);})
    });
    $("#samples_tab .samplestbl tbody").empty().append(rendered);
  });    
}

let attach_toolbar_btns = function() {
    var tab_toolbar = `<span id="new_sample"><i class="fa-solid fa-plus fa-lg"></i></span>`;
    var toolbar_rendered = $(tab_toolbar);
    $("#toolbar_for_tab").append(toolbar_rendered);
    if(is_locked) { $("#toolbar_for_tab").find("#new_sample").addClass("d-none"); }
    $("#new_sample").on("click", function(e){ $("#samples_tab").data("edit_sample")({})});
};

let attachSampleChangeListener = function(trgt) {
  trgt.querySelector(".tabcontainer").addEventListener("lg.DAQSampleChanged", () => { 
    console.log("The current sample changed in the DAQ. Refreshing this page");
    refreshTab();
  })
};


let refreshTab = function() { }

export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer alwaysreload" id="samples_tab">
    <div class="container-fluid text-center" id="sample_content">
      <div class="table-responsive">
        <table class="table table-condensed table-striped table-bordered samplestbl">
          <thead><tr><th>Name</th><th>Description</th><th>Actions</th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;

  attach_toolbar_btns();
  loadSampleData();
  attachSampleChangeListener(trgt);

  refreshTab = function() { 
    loadSampleData();
  }
}