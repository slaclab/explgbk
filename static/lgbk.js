/*
 * Sets the current sample in the logbook titlebar.
 */
var setCurrentUISample = function() {
     var template = `<span><i class="fas fa-snowflake fa-lg" aria-hidden="true"></i></span>
     <span id="current_sample_name" class="ttip">{{ sample_showing_in_UI }}</span>`;
     Mustache.parse(template);
     var ttip_template = `<span class="ttiptext">
       <p>While the UI is showing data for <strong>{{ sample_showing_in_UI }}</strong>, the DAQ is currently processing <strong>{{ current_sample_at_DAQ }}</strong>.</p>
       <p>To change the sample being displayed in the UI, please click on the sample name and choose the current sample.</p>
     </span>`;
     Mustache.parse(ttip_template);
     var choose_sample_template = `{{#sample_names}}<tr data-sample="{{.}}"><td><span class="chsmpic"><i class="far fa-hand-point-right fa-lg"></i><span></td><td>{{.}}</td></tr>{{/sample_names}}`;
     Mustache.parse(choose_sample_template);
     $("#current_sample_lbl").removeClass("samples_different");
     $("#current_sample_lbl").prop("title", "");
     if(sample_showing_in_UI) {
         var samplesDict = {sample_showing_in_UI:sample_showing_in_UI, current_sample_at_DAQ:current_sample_at_DAQ};
         var rendered = $(Mustache.render(template, samplesDict));
         $("#current_sample_lbl").html(rendered);
         if(sample_showing_in_UI != current_sample_at_DAQ) {
             $("#current_sample_lbl").addClass("samples_different");
             $("#current_sample_name").tooltip({html: true, delay: 500, title: Mustache.render(ttip_template, samplesDict)});
         }
         $("#current_sample_name").parent().on("click", function(){
             $.when($.ajax("../../static/html/ms/chooseSample.html"), $.getJSON("ws/samples"))
             .done(function(d1, d2){
                 var tmpl = d1[0], samples = d2[0], sample_names = _.union(_.map(samples.value, "name"), ["Current Sample", "All Samples"]);
                 Mustache.parse(tmpl);
                 var rendered = $(Mustache.render(tmpl, samplesDict));
                 rendered.find("#choose_sample tbody").append($(Mustache.render(choose_sample_template, {sample_names: sample_names})));
                 rendered.find("#choose_sample tbody tr").on("click", function(){
                     var selected_sample = $(this).attr("data-sample");
                     if(selected_sample == "All Samples") {
                         sample_showing_in_UI = "All Samples";
                     } else if (selected_sample == "Current Sample") {
                         sample_showing_in_UI = current_sample_at_DAQ;
                     } else{
                         sample_showing_in_UI = selected_sample;
                     }
                     $("#glbl_modals_go_here").find(".edit_modal").modal("hide");
                     setCurrentUISample();
                     $(".tabcontainer").trigger("lg.refresh");
                 });
                 $("#glbl_modals_go_here").append(rendered);
                 $("#glbl_modals_go_here").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#glbl_modals_go_here").empty(); });
                 $("#glbl_modals_go_here").find(".edit_modal").modal("show");
           });
       });
     } else {
         $("#current_sample_lbl").empty();
     }
}

/*
 * Get the value of the first URL parameter with the given name.
 * Note that there can be more than one parameter with the same name; if need be, extend this to return an array later.
 */
var getURLParameter = function(paramName) {
	var queryString = window.location.search;
	if(!_.isNil(queryString) && queryString.length > 2) {
		var queries = queryString.substring(1).split("&");
		for ( i = 0, l = queries.length; i < l; i++ ) {
			var parts = queries[i].split('='), name = parts[0], val =  decodeURIComponent(parts[1]);
            if(name == paramName) {
                return val;
            }
		}
	}
    return null;
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

var lgbk_create_edit_exp = function(expInfo) {
  var show_validation_message = function(message) {
        $("#exp_mdl_holder").find(".validation_message").html(message);
        $("#exp_mdl_holder").find(".validation_modal").modal("show");
  }
  if(/.+\(.+\)/.test(expInfo['contact_info'])) {
    expInfo['contact_info_name'] = expInfo['contact_info'].split("(")[0];
    expInfo['contact_info_email'] = expInfo['contact_info'].split("(")[1].split(")")[0];
  } else {
    expInfo['contact_info_name'] = expInfo['contact_info'];
    expInfo['contact_info_email'] = expInfo['contact_info'];
  }
  expInfo['paramkvs'] = _.map(expInfo['params'], function(value, key) { return { key: key, value: value };});
  $.when($.ajax ("../static/html/ms/expreg.html"), $.getJSON(instruments_url), $.getJSON("naming_conventions"), $.getJSON("get_modal_param_definitions", { modal_type: "experiments" }))
  .done(function( d1, d2, d3, d4) {
    var tmpl = d1[0], instruments = d2[0], options = `{{#value}}<option value="{{ _id }}">{{ _id }}</option>{{/value}}`, site_naming_conventions = _.get(d3[0], "value", {}), ignore_experiment_name_regex = false, site_options = d4[0].value;
    Mustache.parse(tmpl); Mustache.parse(options);
    if(_.has(site_naming_conventions, "experiment.name.placeholder")) { expInfo.name_placeholder = _.get(site_naming_conventions, "experiment.name.placeholder"); }
    if(_.has(site_naming_conventions, "experiment.name.tooltip")) { expInfo.name_tooltip = _.get(site_naming_conventions, "experiment.name.tooltip"); }
    if(_.get(site_options, "options.disable_posix")) { expInfo.disable_posix = true; }
    var rendered = $(Mustache.render(tmpl, expInfo));
    rendered.find(".start_time").datetimepicker({defaultDate: moment(expInfo['start_time']), sideBySide: true });
    rendered.find(".end_time").datetimepicker({defaultDate: moment(expInfo['end_time']), sideBySide: true });
    rendered.find(".instrument").append($(Mustache.render(options, instruments)));
    rendered.find(".instrument").val(expInfo['instrument']);
    rendered.find(".fa-plus").parent().on("click", function(){ $(this).closest("tr").after($(this).closest("tr").clone(true).find("input").val("").end()); });
    rendered.find(".fa-trash").parent().on("click", function(){ $(this).closest("tr").remove(); });
    rendered.find(".experiment_name").on("change", function(){
      let urexpname = $(this).val();
      console.log("Checking to see if experiment " + urexpname + " is registered in URAWI");
      $.getJSON(lookup_experiment_in_urawi, {"experiment_name": urexpname})
      .done(function (expdata) {
        console.log(expdata);
        if(expdata.success) {
          rendered.find(".description").val(expdata.value['proposalTitle']);
          rendered.find(".pi_name").val(_.get(expdata.value, 'spokesPerson.firstName') + " " + _.get(expdata.value,'spokesPerson.lastName'));
          rendered.find(".pi_email").val(_.get(expdata.value, 'spokesPerson.email'));
          rendered.find(".leader_account").val(_.get(expdata.value, 'spokesPerson.account[0].unixName'));
          rendered.find(".posix_group").val(urexpname);
          if (_.get(expdata.value, 'proposalInstrument') != "") { rendered.find(".instrument").val(_.get(expdata.value, 'proposalInstrument')) };
          if (_.get(expdata.value, "startDate") != "") { rendered.find('.start_time').datetimepicker('date', moment(_.get(expdata.value, "startDate"))) };
          if (_.get(expdata.value, "stopDate") != "") { rendered.find('.end_time').datetimepicker('date', moment(_.get(expdata.value, "stopDate"))) };
        }
      });
    });
    if (_.has(expInfo, "name")) { rendered.find(".register_btn").text("Update"); }
    rendered.find(".register_btn").on("click", function(e) {
      e.preventDefault();
      var formObj = $("#exp_mdl_holder").find("form");
      var validations = [
          [function() { return $.trim(formObj.find(".experiment_name").val()) == ""; }, "Experiment name cannot be blank."],
          [function() { return $.trim(formObj.find(".instrument").val()) == ""; }, "Please choose a valid instrument."],
          [function() { return $.trim(formObj.find(".start_time input").val()) == ""; }, "Please choose a valid start time."],
          [function() { return $.trim(formObj.find(".end_time input").val()) == ""; }, "Please choose a valid end time."],
          [function() { return formObj.find('.end_time').datetimepicker('date').isSameOrBefore(formObj.find('.start_time').datetimepicker('date'), 'minute') ; }, "The end time should be after the start time."],
          [function() { return $.trim(formObj.find(".leader_account").val()) == ""; }, "Please specify the UNIX account of the leader for the experiment. This user will have privileges to add and remove collaborators from the experiment."],
          [function() { return $.trim(formObj.find(".pi_name").val()) == ""; }, "Please specify the full name of the principal investigator."],
          [function() { return $.trim(formObj.find(".pi_email").val()) == ""; }, "Please specify the email address for the principal investigator."],
          [function() {
            var email = $.trim(formObj.find(".pi_email").val());
            var re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
            return !re.test(email.toLowerCase());
            }, "Please specify the email address for the principal investigator."],
          [function() { return $.trim(formObj.find(".description").val()) == ""; }, "A brief description of the experiment is very helpful."],
          [function() { return formObj.find("tbody tr").map(function() { return $(this).find("input.key").val() == "" ^ $(this).find("input.value").val() == ""; }).toArray().reduce(function(a, b) { return a + b; }, 0); }, "Every param that has a name must have a value and vice versa."],
          [function() { return _.isEmpty($.trim(formObj.find(".experiment_name_original").val())) && !_.isEmpty($.trim(formObj.find(".inital_sample").val())) && !/^[\w/_-]+$/.test($.trim(formObj.find(".inital_sample").val())); }, "Please restrict sample names to alphanumeric characters, dashes, slashes and underscores."],
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
      if(!ignore_experiment_name_regex && _.has(site_naming_conventions, "experiment.name.validation_regex")) {
          let exp_nam_regex = new RegExp(_.get(site_naming_conventions, "experiment.name.validation_regex"));
          if(!exp_nam_regex.test(experiment_name)) {
              $("#exp_mdl_holder").find(".validation_message").html("The experiment name " + experiment_name + " does not match the naming convention for this site.");
              $("#exp_mdl_holder").find(".ignore_button").removeClass("d-none").on("click", function(){ ignore_experiment_name_regex = true; $("#exp_mdl_holder").find(".validation_modal").modal("hide"); });
              $("#exp_mdl_holder").find(".validation_modal").modal("show");
              v_failed = true;
              return false;
          }
      }
      var original_experiment_name = $.trim(formObj.find(".experiment_name_original").val());
      var updating_existing_experiment = (original_experiment_name == experiment_name);
      var exp_params = {};
      formObj.find("tbody tr").map(function() {  var key = $(this).find("input.key").val(), val = $(this).find("input.value").val(); if(key != "" && val != "") { exp_params[key] = val; }});
      var registration_doc = {
          "name" : experiment_name,
          "instrument" : $.trim(formObj.find(".instrument").val()),
          "description" : $.trim(formObj.find(".description").val()),
          "start_time" : formObj.find('.start_time').datetimepicker('date').toJSON(),
          "end_time" : formObj.find('.end_time').datetimepicker('date').toJSON(),
          "leader_account" : $.trim(formObj.find(".leader_account").val()),
          "contact_info" : $.trim(formObj.find(".pi_name").val()) + " (" + $.trim($(".pi_email").val()) + ")",
          "posix_group" : $.trim(formObj.find(".posix_group").val()),
          "params": exp_params
      };
      if(!updating_existing_experiment && !_.isEmpty($.trim(formObj.find(".inital_sample").val()))) {
          registration_doc["initial_sample"] = $.trim(formObj.find(".inital_sample").val());
      }

      $.ajax({
        type: "POST",
        contentType: "application/json; charset=utf-8",
        url: (updating_existing_experiment ? update_experiment_url : register_experiment_url) + "?experiment_name=" + encodeURIComponent(experiment_name),
        data: JSON.stringify(registration_doc),
        dataType: "json"
      })
      .done(function(data, textStatus, jqXHR) {
        if(data.success) {
            console.log("Successfully submitted experiment " + experiment_name);
            $("#exp_mdl_holder").find(".edit_modal").modal("hide");
            sessionStorage.setItem("ops_active_tab", "experiments");
            sessionStorage.setItem("scroll_to_exp_id", _.replace(experiment_name, " ", "_"));
            window.scrollToExperiment = true;
            setTimeout(function(){ $(document).trigger("experiments", {"CRUD": "Create", value: { name: experiment_name }}) }, 3000);
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
};


var put_instrument_in_standby = function() {
    var instr = $(this).attr("data-instrument");
    var station = $(this).attr("data-station");
    console.log("Putting " + instr + "/" + station + " into standby/maintenance mode.");
    $.ajax({
        type: "POST",
        contentType: "application/json; charset=utf-8",
        url: instrument_standby_url,
        data: JSON.stringify({"instrument": instr, "station": station}),
        dataType: "json"
    })
    .done(function(data){
        if(data.success) {
            console.log("Successfully put "+ instr + "/" + station + " into standby/maintenance mode.");
            location.reload();
        } else {
            alert("Server side exception switching experiment " + data.errormsg);
        }
    })
    .fail( function(jqXHR, textStatus, errorThrown) { alert("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
};

var clone_experiment = function(src_experiment_name, mdl_holder, path_to_ws="", auto_scroll=true) {
  console.log("Cloning experiment " + src_experiment_name);
  $.ajax (path_to_ws + "../static/html/ms/expclone.html")
  .done(function( tmpl ) {
    Mustache.parse(tmpl);
    var rendered = $(Mustache.render(tmpl, {src_experiment_name: src_experiment_name, name: src_experiment_name, cloning: true, clone_attrs: [{k: "Experimental Setup", v: "setup"}, {k: "Samples", v: "samples"}, {k: "Roles", v: "roles"}, {k: "Run Parameter Descriptions", v: "run_param_descriptions"}]}));
    let show_validation_message = function(message) {
        rendered.find(".validation_message").text(message).removeClass("d-none");
    }
    rendered.find(".start_time").datetimepicker({defaultDate: moment(), sideBySide: true });
    rendered.find(".end_time").datetimepicker({defaultDate: moment().add(2, 'days'), sideBySide: true });
    rendered.find(".clone_btn").on("click", function(e) {
      e.preventDefault();
      var formObj = rendered.find("form");
      var validations = [
          [function() { return $.trim(formObj.find(".experiment_name").val()) == ""; }, "Experiment name cannot be blank."],
          [function() { return $.trim(formObj.find(".experiment_name").val()) == formObj.find(".src_experiment_name").val(); }, "Experiment name cannot be the same as the original."],
          [function() { return $.trim(formObj.find(".start_time input").val()) == ""; }, "Please choose a valid start time."],
          [function() { return $.trim(formObj.find(".end_time input").val()) == ""; }, "Please choose a valid end time."],
          [function() { return formObj.find('.end_time').datetimepicker('date').isSameOrBefore(formObj.find('.start_time').datetimepicker('date'), 'minute') ; }, "The end time should be after the start time."]
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
      var registration_doc = {
          "name" : experiment_name,
          "start_time" : formObj.find('.start_time').datetimepicker('date').toJSON(),
          "end_time" : formObj.find('.end_time').datetimepicker('date').toJSON()
      };
      formObj.find(".clone_attr:checked").each(function(){ registration_doc[$(this).attr("name")] = true; });
      console.log(registration_doc);

      let clone_experiment_url = path_to_ws + "ws/clone_experiment";
      $.ajax({
        type: "POST",
        contentType: "application/json; charset=utf-8",
        url: clone_experiment_url + "?experiment_name=" + encodeURIComponent(experiment_name) + "&src_experiment_name=" + encodeURIComponent(src_experiment_name),
        data: JSON.stringify(registration_doc),
        dataType: "json"
      })
      .done(function(data, textStatus, jqXHR) {
        if(data.success) {
            console.log("Successfully cloned experiment " + experiment_name);
            mdl_holder.find(".edit_modal").modal("hide");
            if(auto_scroll) {
                sessionStorage.setItem("ops_active_tab", "experiments");
                sessionStorage.setItem("scroll_to_exp_id", _.replace(experiment_name, " ", "_"));
            }
            window.scrollToExperiment = true;
            setTimeout(function(){ $(document).trigger("experiments", {"CRUD": "Create", value: { name: experiment_name }}) }, 3000);
        } else {
          show_validation_message("Server failure: " + data.errormsg);
        }
      })
      .fail( function(jqXHR, textStatus, errorThrown) { show_validation_message("Server failure: " + _.get(jqXHR, "responseText", textStatus))})
    });
   mdl_holder.empty().append(rendered);
   mdl_holder.find(".edit_modal").on("hidden.bs.modal", function(){ mdl_holder.empty(); });
   mdl_holder.find(".edit_modal").modal("show");
  });
};

var elog_timezone = "America/Los_Angeles";
var elog_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(elog_timezone).format("MMM/D/YYYY")}};
var elog_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(elog_timezone).format("MMM/D/YYYY HH:mm:ss")}};
if(sessionStorage.getItem("use_local_timezone") != null && sessionStorage.getItem("use_local_timezone")) {
    console.log("Using local timezone from the browser");
    elog_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY")}};
    elog_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY HH:mm:ss")}};
}

var success_message = function(msg, timeout=5000) {
    new Noty( { text: msg, layout: "topRight", type: "success", timeout: timeout }).show();
}

var error_message = function(msg, timeout=5000) {
    new Noty( { text: msg, layout: "topRight", type: "error", timeout: timeout }).show();
}

let delayFunction = function(fn, ms=500) {
    // Function to execute some other function after a delay; resetting each time this is called.
    // https://stackoverflow.com/questions/1909441/how-to-delay-the-keyup-handler-until-the-user-stops-typing
    let timer = 0
    return function(...args) {
        clearTimeout(timer)
        timer = setTimeout(fn.bind(this, ...args), ms || 0)
    }
}
