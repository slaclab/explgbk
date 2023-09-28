export function export_as_csv(e) {
    let params = {}; params["runtable"] = $("#rtbl_tab .nav-pills a.active").attr("data-rtbl-name");
    if(sample_showing_in_UI != null && sample_showing_in_UI != "All Samples") { params["sampleName"] = sample_showing_in_UI; }
    window.open("ws/runtables/export_as_csv?" + $.param(params), "_blank");
}

export function delete_rtbl_fn(e) {
    let clkRTblName = $("#rtbl_tab .nav-pills a.active").attr("data-rtbl-name"), is_system_run_table = _.get($("#rtbl_tab").data("tblData")[clkRTblName], 'is_system_run_table', false);
    let yesnomsg = is_system_run_table ? "<div><b>" + clkRTblName + "</b> is a system run table. Deleting a system run table also deletes the run table for other experiments.</div><div>Are you sure you want to do this?</div>" : "Do you want to delete the experiment run table <b>" + clkRTblName + "</b>?";
    $.ajax ("../../static/html/ms/generic_yes_no.html")
    .done(function( tmpl ) {
      Mustache.parse(tmpl);
      var rendered = $(Mustache.render(tmpl, {"title": "Delete run table", "message": yesnomsg }));
      rendered.find(".yesbutton").on("click", function(e) {
        $.ajax({ url: "ws/delete_run_table", "data": { table_name: clkRTblName, is_system_run_table: is_system_run_table }, method: "DELETE"})
        .done(function(data) { if(_.get(data, "success", true)) { window.location.reload(true); } else { alert("Server side error deleting run table " + data.errormsg); }})
        .fail(function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure deleting run table " + textStatus); })
      });
      $("#rtbl_tab").find(".mdl_holder").empty().append(rendered);
      $("#rtbl_tab").find(".mdl_holder").find(".modal").on("hidden.bs.modal", function(){ $("#rtbl_tab").find(".mdl_holder").empty(); });
      $("#rtbl_tab").find(".mdl_holder").find(".modal").modal("show");
    })
}

export function clone_rtbl_fn(e) {
    var clkRTblName = $("#rtbl_tab .nav-pills a.active").attr("data-rtbl-name");
    $.ajax("../../static/html/ms/gen_clone.html")
    .done(function(tmpl){
        Mustache.parse(tmpl);
        var t_tmpl = `Clone run table {{ existing_object_name }}`,
            title = Mustache.render(t_tmpl, {existing_object_name: clkRTblName}),
            rendered = $(Mustache.render(tmpl, {title: title, txtlbl: 'New run table name:', btnlbl: "Clone"}));
        rendered.find("#obj_clone_btn").on("click", function(e){
            console.log("Cloning a run table definition");
            e.preventDefault();
            var formObj = $("#rtbl_tab").find(".mdl_holder").find("form");
            var validations = [
                [function() { return $.trim(formObj.find(".new_object_name").val()) == ""; }, "The name of the cloned table cannot be blank."],
                [function() { return !/^([\w-\s]+)$/.test($.trim(formObj.find(".new_object_name").val()))}, "We limit the special characters that can be used in table names.  Alpha-numeric with underscores and spaces only."],
                [function() { return _.find($("#rtbl_tab").data("tblData"), function(shf){return shf.name == $.trim(formObj.find(".new_object_name").val())}) != undefined }, "The run table name already exists."]
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
            $.getJSON({url: "ws/clone_run_table_def"+ "?existing_run_table_name=" + encodeURIComponent(clkRTblName) + "&new_run_table_name=" + encodeURIComponent($.trim(formObj.find(".new_object_name").val())), method: "POST"})
            .done(function(data, textStatus, jqXHR) {
                if(data.success) {
                    console.log("Successfully cloned run table " + clkRTblName);
                    $("#rtbl_tab").find(".mdl_holder").find(".edit_modal").modal("hide");
                    window.location.reload(true);
                } else {
                    alert("Server side exception cloning run table " + data.errormsg);
                }
            })
            .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure cloning run table " + textStatus); })
        });

        $("#rtbl_tab").find(".mdl_holder").append(rendered);
        $("#rtbl_tab").find(".mdl_holder").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#rtbl_tab").find(".mdl_holder").empty(); });
        $("#rtbl_tab").find(".mdl_holder").find(".edit_modal").modal("show");
    });
}

export function clone_sys_tmpl_rtbls(e) {
  console.log("Cloning all system template run tables into this experiment");
  $.getJSON("ws/clone_system_template_run_tables")
  .done(function(data, textStatus, jqXHR) { if(data.success) { window.location.reload(true); } else { error_message("Server side exception cloning run table " + data.errormsg)} })
  .fail( function(jqXHR, textStatus, errorThrown) { error_message("Server side HTTP failure cloning run table " + textStatus); })
}

export function make_system_runtable(e) {
    var clkRTblName = $("#rtbl_tab .nav-pills a.active").attr("data-rtbl-name");
    $.ajax("../../static/html/ms/make_system_runtable.html")
    .done(function(tmpl){
        Mustache.parse(tmpl);
        var rendered = $(Mustache.render(tmpl, { run_table_name: clkRTblName, instrument: instrument_name }));
        rendered.find("#obj_clone_btn").on("click", function(e){
            console.log("Replacing system run table");
            e.preventDefault();
            var formObj = $("#rtbl_tab").find(".mdl_holder").find("form");
            var validations = [
                [function() { return $.trim(formObj.find(".new_object_name").val()) == ""; }, "The name of the system run table cannot be blank."],
                [function() { return !/^([\w-\s]+)$/.test($.trim(formObj.find(".new_object_name").val()))}, "We limit the special characters that can be used in table names. Alpha-numeric with underscores and spaces only."]
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
            $.getJSON({url: "ws/replace_system_run_table_def", data: { existing_run_table_name: clkRTblName, system_run_table_name: $.trim(formObj.find(".new_object_name").val()), is_instrument: formObj.find(".instrument_only").is(":checked"), is_template: formObj.find(".is_template").is(":checked") } , method: "POST"})
            .done(function(data, textStatus, jqXHR) {
                if(data.success) {
                    console.log("Successfully replaced system run table with " + clkRTblName);
                    $("#rtbl_tab").find(".mdl_holder").find(".edit_modal").modal("hide");
                    window.location.reload(true);
                } else {
                    alert("Server side exception replacing system run table " + data.errormsg);
                }
            })
            .fail( function(jqXHR, textStatus, errorThrown) { alert("Server side HTTP failure replacing system run table " + textStatus); })
        });

        $("#rtbl_tab").find(".mdl_holder").append(rendered);
        $("#rtbl_tab").find(".mdl_holder").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#rtbl_tab").find(".mdl_holder").empty(); });
        $("#rtbl_tab").find(".mdl_holder").find(".edit_modal").modal("show");
    });
}
