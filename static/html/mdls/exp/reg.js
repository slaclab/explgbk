let getURAWIRegistration = function(modalElem, startDate, endDate, event) {
  let urexpname = event.target.value;
  console.log("Checking to see if experiment " + urexpname + " is registered in URAWI");
  let exp_params = new URLSearchParams();
  exp_params.append("experiment_name", urexpname);
  modalElem.querySelectorAll("lgbk-custom-param").forEach((lcp) => {  let key = lcp.name, val = lcp.value; if(key != "" && val != "") { exp_params.set(key, val); }  })


  fetch(lgbkabspath("/lgbk/ws/lookup_experiment_in_urawi?"+exp_params.toString()), {cache: "no-store"})
  .then(function (resp) { return resp.json() })
  .then(function (expdataresp) {
    if(expdataresp.success) {
      let expdata = expdataresp.value;
      console.log(expdata);
      modalElem.querySelector(".description").value = expdata['proposalTitle'];
      modalElem.querySelector(".pi_name").value = _.get(expdata, 'spokesPerson.firstName') + " " + _.get(expdata,'spokesPerson.lastName');
      modalElem.querySelector(".pi_email").value = _.get(expdata, 'spokesPerson.email');
      modalElem.querySelector(".leader_account").value = _.get(expdata, 'spokesPerson.account[0].unixName');
      modalElem.querySelector(".posix_group").value = urexpname;
      if (_.get(expdata, 'instrument') !== "") {
        let sel = _.find(Array.from(modalElem.querySelectorAll(".instrument option")), (x) => { return _.toUpper(x.value) === _.toUpper(expdata["instrument"]) });
        if(_.isNil(sel)) { error_message("Can't find the selection for instrument " + expdata["instrument"]); return; }
        modalElem.querySelector(".instrument").value = sel.value;
      };
      if (_.get(expdata, "startDate") != "") { startDate.dates.setValue(new tempusDominus.DateTime(moment(_.get(expdata, "startDate")).toDate())) };
      if (_.get(expdata, "stopDate") != "") { endDate.dates.setValue(new tempusDominus.DateTime(moment(_.get(expdata, "stopDate")).toDate())) };
    }
  });
}

let form2doc = function(formElem, startDate, endDate) {
  let registration_doc = {"params": {}};
  registration_doc["name"] = _.trim(formElem.querySelector(".experiment_name").value);
  registration_doc["instrument"] = _.trim(formElem.querySelector(".instrument").value)
  registration_doc["description"] = _.trim(formElem.querySelector(".description").value)
  registration_doc["leader_account"] = _.trim(formElem.querySelector(".leader_account").value)
  let pi_name = _.trim(formElem.querySelector(".pi_name").value), pi_email = _.trim(formElem.querySelector(".pi_email").value);
  if(pi_name !== "" && pi_email !== "") {
    registration_doc["contact_info"] =  pi_name + " (" + pi_email + ")"
  }
  registration_doc["posix_group"] = _.trim(formElem.querySelector(".posix_group").value)
  registration_doc["start_time"] = startDate.viewDate.toJSON();
  registration_doc["end_time"] = endDate.viewDate.toJSON();

  let iselem = formElem.querySelector(".inital_sample");
  if(!_.isNil(iselem)){
    let initial_sample = _.trim(iselem.value);
    if(initial_sample !== "") {
      registration_doc["initial_sample"] = initial_sample;
    }
  }

  formElem.querySelectorAll("lgbk-custom-param").forEach((lcp) => { lcp.mergeinto(registration_doc["params"]) });
  return registration_doc;
}

let error_message = function(message) {
  document.querySelector("#glbl_modals_go_here .errormsg").innerText = message;
  document.querySelector("#glbl_modals_go_here .errormsg").classList.remove("d-none");
}

let checkCustomParams = function(formElem){
  return Array.from(formElem.querySelectorAll("lgbk-custom-param")).every((lcp) => { return lcp.validate(error_message)})
}

let checkRequiredFields = function(registration_doc) { 
  let requiredFailed = [
    ["name", "Experiment name cannot be blank."],
    ["instrument", "Please choose a valid instrument."],
    ["leader_account", "Please specify the UNIX account of the leader for the experiment. This user will have privileges to add and remove collaborators from the experiment."],
    ["contact_info", "Please specify the contact details (full name and email) of the principal investigator."],
    ["description", "A brief description of the experiment is very helpful."],
    ["start_time", "Please choose a valid start time."],
    ["end_time", "Please choose a valid end time."]
  ].every((v) => {
    let val = _.get(registration_doc, v[0], "");
    if(val === "") { error_message(v[1]); return false; }
    return true;
  })
  return requiredFailed;
}

let checkOtherValidations = function(registration_doc) { 
  // Check end data is after start date.
  if(!moment(registration_doc["end_time"]).isAfter(moment(registration_doc["start_time"]))) {
    error_message("The end time should be after the start time."); return false;
  }
  // Check if contact details is parse'able
  const pire = /^([^\()]+)\((([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))\)$/;
  if(!pire.test(registration_doc["contact_info"].toLowerCase())) {
    error_message("Please specify the email address for the principal investigator."); return false;
  }

  const nmre = /^[\w/_-]+$/;
  if(!nmre.test(registration_doc["name"]) || (_.has(registration_doc, "initial_sample") && !nmre.test(registration_doc["initial_sample"]))) {
    error_message("Please restrict experiment and sample names to alphanumeric characters, dashes, slashes and underscores."); return false;
  }

  return true;
}

let ignore_naming_convention_for_experiment_name = null;

let checkExperimentNamingConvention = function(registration_doc, site_naming_conventions) {
  const experiment_name = registration_doc["name"];
  if(_.has(site_naming_conventions, "experiment.name.validation_regex") && experiment_name !== ignore_naming_convention_for_experiment_name) {
    let exp_nam_regex = new RegExp(_.get(site_naming_conventions, "experiment.name.validation_regex"));
    if(!exp_nam_regex.test(experiment_name)) {
      error_message("The experiment name " + experiment_name + " does not match the naming convention for this site. You can override this by clicking on the Register button once more.");
      ignore_naming_convention_for_experiment_name = experiment_name;
      return false;
    }
  }
  return true;
}

export function lgbk_create_edit_exp(expInfo, customizer) {
    if(/.+\(.+\)/.test(expInfo['contact_info'])) {
      expInfo['contact_info_name'] = expInfo['contact_info'].split("(")[0];
      expInfo['contact_info_email'] = expInfo['contact_info'].split("(")[1].split(")")[0];
    } else {
      expInfo['contact_info_name'] = expInfo['contact_info'];
      expInfo['contact_info_email'] = expInfo['contact_info'];
    }
    expInfo['paramkvs'] = _.map(expInfo['params'], function(value, key) { return { key: key, value: value };});

    Promise.all([fetch(lgbkabspath("/static/html/mdls/exp/reg.html")), fetch(lgbkabspath("/lgbk/ws/instruments")), fetch(lgbkabspath("/lgbk/naming_conventions")), fetch(lgbkabspath("/lgbk/get_modal_param_definitions?modal_type=experiments"))])
    .then((resps) => { if(resps.some((x) => !x.ok)){  return Promise.reject(new Error())}; return Promise.all([resps[0].text(), resps[1].json(), resps[2].json(), resps[3].json()])})
    .then((vals) => {
        let [ d1, d2, d3, d4 ] = vals;
        var tmpl = d1, instruments = d2.value, site_naming_conventions = _.get(d3, "value", {}), site_options = d4.value;
        Mustache.parse(tmpl);
        if(_.has(site_naming_conventions, "experiment.name.placeholder")) { expInfo.name_placeholder = _.get(site_naming_conventions, "experiment.name.placeholder"); }
        if(_.has(site_naming_conventions, "experiment.name.tooltip")) { expInfo.name_tooltip = _.get(site_naming_conventions, "experiment.name.tooltip"); }
        if(_.get(site_options, "options.disable_posix")) { expInfo.disable_posix = true; }
        expInfo.instruments = instruments;
        console.log(expInfo);
        document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(tmpl, expInfo);
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");
        const myModal = new bootstrap.Modal(modalElem);
        modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
        modalElem.querySelector(".instrument").value = expInfo['instrument'];
        modalElem.querySelectorAll("lgbk-custom-param").forEach((lcp) => lcp.setAddTemplate('<lgbk-custom-param class="row"/>'));
        let startDate = new tempusDominus.TempusDominus(modalElem.querySelector("#expreg_start_time_picker"), {defaultDate: moment(expInfo['start_time']).toDate(), display: {sideBySide: true} });
        let endDate = new tempusDominus.TempusDominus(modalElem.querySelector("#expreg_end_time_picker"), {defaultDate: moment(expInfo['end_time']).toDate(), display: {sideBySide: true} });
        if(!_.isNil(customizer)) { customizer.customize(modalElem, formElem, expInfo) }

        if (_.has(expInfo, "name")) { modalElem.querySelector(".register_btn").innerText = "Update"; }
        modalElem.querySelector(".experiment_name").addEventListener("change", _.partial(getURAWIRegistration, modalElem, startDate, endDate));


        modalElem.querySelector(".register_btn").addEventListener("click", function(event) {
          event.preventDefault();
          if(!checkCustomParams(formElem)) return;
          let registration_doc = form2doc(formElem, startDate, endDate), experiment_name = registration_doc["name"];
          console.log(registration_doc);
          document.querySelector("#glbl_modals_go_here .errormsg").innerText = "";
          if(!checkRequiredFields(registration_doc)) return;
          if(!checkOtherValidations(registration_doc)) return;
          if(!_.isNil(customizer)) { if(!customizer.validate(modalElem, formElem, registration_doc, error_message)) { return } }
          if(!_.has(expInfo, "name") && !checkExperimentNamingConvention(registration_doc, site_naming_conventions)) return;

          async function checkHTTPResponse(resp) {
            if(!resp.ok) {
                let respdata = await resp.text(); 
                return Promise.reject(new Error(resp.statusText + " --> " + respdata));
            }
            return resp.json();
          }
      
          function checkStatus(status) {
            console.log(status); 
            if(!_.get(status, "success", false)) {
                return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
            }; 
            if(!_.isNil(customizer)) {
              customizer.onCompletion(myModal, formElem, registration_doc, error_message);
            } else {
              sessionStorage.setItem("scroll_to_exp_id", _.replace(experiment_name, " ", "_"));
              myModal.hide();
            }
            return true; 
        }
        
        if(_.has(expInfo, "name")) {
          let updateExperimentURL = lgbkabspath("/lgbk/ws/experiment_edit_info") + "?experiment_name=" + encodeURIComponent(registration_doc["name"])
          fetch(updateExperimentURL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(registration_doc) })
          .then(checkHTTPResponse)
          .then(checkStatus)
          .catch((errmsg) => { error_message(errmsg) })
        } else {
          let registerExperimentURL = lgbkabspath("/lgbk/ws/register_new_experiment") +  "?experiment_name=" + encodeURIComponent(registration_doc["name"])
          fetch(registerExperimentURL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(registration_doc) })
          .then(checkHTTPResponse)
          .then(checkStatus)
          .catch((errmsg) => { error_message(errmsg) })
        }
      });
      
      myModal.show();
    })
    .catch((error) => {console.log(error)});
  }