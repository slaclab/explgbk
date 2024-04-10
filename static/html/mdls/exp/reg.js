import { getURAWIRegistration } from "./fns.js";


const patch_modal_defs = (mdlparams) => {
  console.log(mdlparams);
}


let form2doc = function(formElem, startDate, endDate) {
  let registration_doc = {"params": {}};
  formElem.querySelectorAll("[data-lg-attr]").forEach((e) => {
    const val = _.trim(e.value);
    if(!_.isNil(val)) {
      _.set(registration_doc, e.getAttribute("data-lg-attr"), val);
    }
  });

  let pi_name = _.trim(formElem.querySelector(".pi_name").value), pi_email = _.trim(formElem.querySelector(".pi_email").value);
  if(pi_name !== "" && pi_email !== "") {
    registration_doc["contact_info"] =  pi_name + " (" + pi_email + ")"
  }
  registration_doc["start_time"] = startDate.viewDate.toJSON();
  registration_doc["end_time"] = endDate.viewDate.toJSON();

  formElem.querySelectorAll("lgbk-custom-param").forEach((lcp) => { lcp.mergeinto(registration_doc["params"]) });
  return registration_doc;
}

let errormsg = function(message) {
  document.querySelector("#glbl_modals_go_here .errormsg").innerText = message;
  document.querySelector("#glbl_modals_go_here .errormsg").classList.remove("d-none");
}

let checkCustomParams = function(formElem){
  return Array.from(formElem.querySelectorAll("lgbk-custom-param")).every((lcp) => { return lcp.validate(errormsg)})
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
    if(val === "") { errormsg(v[1]); return false; }
    return true;
  })
  return requiredFailed;
}

let checkOtherValidations = function(registration_doc) { 
  // Check end data is after start date.
  if(!moment(registration_doc["end_time"]).isAfter(moment(registration_doc["start_time"]))) {
    errormsg("The end time should be after the start time."); return false;
  }
  // Check if contact details is parse'able
  const pire = /^([^\()]+)\((([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))\)$/;
  if(!pire.test(registration_doc["contact_info"].toLowerCase())) {
    errormsg("Please specify the email address for the principal investigator."); return false;
  }

  return true;
}

let ignore_naming_convention_for_experiment_name = null;

let checkExperimentNamingConvention = function(registration_doc, site_naming_conventions) {
  const experiment_name = registration_doc["name"];
  if(_.has(site_naming_conventions, "experiment.name.validation_regex") && experiment_name !== ignore_naming_convention_for_experiment_name) {
    let exp_nam_regex = new RegExp(_.get(site_naming_conventions, "experiment.name.validation_regex"));
    if(!exp_nam_regex.test(experiment_name)) {
      errormsg("The experiment name " + experiment_name + " does not match the naming convention for this site. You can override this by clicking on the Register button once more.");
      ignore_naming_convention_for_experiment_name = experiment_name;
      return false;
    }
  }
  return true;
}

export function lgbk_create_edit_exp(theexp, onCompletion) {
    if(/.+\(.+\)/.test(theexp['contact_info'])) {
      theexp['contact_info_name'] = theexp['contact_info'].split("(")[0];
      theexp['contact_info_email'] = theexp['contact_info'].split("(")[1].split(")")[0];
    } else {
      theexp['contact_info_name'] = theexp['contact_info'];
      theexp['contact_info_email'] = theexp['contact_info'];
    }
    theexp['paramkvs'] = _.map(theexp['params'], function(value, key) { return { key: key, value: value };});
    const isEditing = _.has(theexp, "name") ? true : false;

    Promise.all([fetch(lgbkabspath("/static/html/mdls/exp/reg.html")), fetch(lgbkabspath("/lgbk/ws/instruments")), fetch(lgbkabspath("/lgbk/naming_conventions")), fetch(lgbkabspath("/lgbk/get_modal_param_definitions?modal_type=expreg"))])
    .then((resps) => { if(resps.some((x) => !x.ok)){  return Promise.reject(new Error())}; return Promise.all([resps[0].text(), resps[1].json(), resps[2].json(), resps[3].json()])})
    .then((vals) => {
        let [ d1, d2, d3, d4 ] = vals;
        var tmpl = d1, instruments = d2.value, site_naming_conventions = _.get(d3, "value", {}), mdldefs = _.get(d4, "value"), mdlparams = _.get(mdldefs, "params", []);
        Mustache.parse(tmpl);
        patch_modal_defs(mdlparams); // Patch legacy modal definitions...        
        theexp.instruments = instruments;
        console.log(theexp);
        document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(tmpl, theexp);
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");
        modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
        modalElem.querySelectorAll("lgbk-custom-param").forEach((lcp) => lcp.setAddTemplate('<lgbk-custom-param class="row"/>'));
        modalElem.querySelectorAll("[data-lg-attr]").forEach((e) => {
          e.value = _.get(theexp, e.getAttribute("data-lg-attr"), "");
          e.dispatchEvent(new Event("change"));
          e.addEventListener("change", (event) => {
            _.set(theexp, event.target.getAttribute("data-lg-attr"), event.target.value);
            console.log(theexp);
          })
        });

        let startDate = new tempusDominus.TempusDominus(modalElem.querySelector("#expreg_start_time_picker"), {defaultDate: moment(theexp['start_time']).toDate(), display: {sideBySide: true} });
        let endDate = new tempusDominus.TempusDominus(modalElem.querySelector("#expreg_end_time_picker"), {defaultDate: moment(theexp['end_time']).toDate(), display: {sideBySide: true} });
        if (isEditing) {
          console.log("We are editing the experiment; turning off non-editable values");
          modalElem.querySelectorAll("[data-lg-noedit]").forEach((elem) => { 
            elem.readOnly = true; 
            elem.disabled = true;
          })
          modalElem.querySelector(".register_btn").innerText = "Update";
        }
        modalElem.querySelector("[data-lg-attr='name']").addEventListener("change", _.partial(getURAWIRegistration, modalElem, startDate, endDate));

        import(lgbkabspath("/static/html/mdls/common/mdlparams.js")).then((mod) => { 
          const { LgbkCustomModalParams } = mod;
          let mdlParamsJS = new LgbkCustomModalParams(mdlparams, errormsg);
          console.log(mdlParamsJS);
          mdlParamsJS.render(theexp);
          mdlParamsJS.patchMainModal(mdldefs, theexp);
          modalElem.querySelectorAll("[data-lg-attr]").forEach((e) => {
            e.value = _.get(theexp, e.getAttribute("data-lg-attr"), "");
            e.dispatchEvent(new Event("change"));
          });
    
          const myModal = new bootstrap.Modal(modalElem);
          myModal.show();
          
          modalElem.querySelector(".register_btn").addEventListener("click", (event) => {
              event.preventDefault();
              modalElem.querySelector(".errormsg").innerHTML = "";

              let registration_doc = form2doc(formElem, startDate, endDate), experiment_name = registration_doc["name"];
              console.log(registration_doc);
              if(!mdlParamsJS.validate(registration_doc)){
                return;
              }

              if(!checkRequiredFields(registration_doc)) return;
              if(!checkOtherValidations(registration_doc)) return;
              if(!_.has(theexp, "name") && !checkExperimentNamingConvention(registration_doc, site_naming_conventions)) return;
              if(!checkCustomParams(formElem)) return;
    
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
                sessionStorage.setItem("scroll_to_exp_id", _.replace(experiment_name, " ", "_"));
                myModal.hide();
                if(!_.isNil(onCompletion)) { onCompletion(registration_doc) }
                return true; 
              }
            
            if(isEditing) {
              let updateExperimentURL = lgbkabspath("/lgbk/ws/experiment_edit_info") + "?experiment_name=" + encodeURIComponent(registration_doc["name"])
              fetch(updateExperimentURL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(registration_doc) })
              .then(checkHTTPResponse)
              .then(checkStatus)
              .catch((errmsg) => { errormsg(errmsg) })
            } else {
              let registerExperimentURL = lgbkabspath("/lgbk/ws/register_new_experiment") +  "?experiment_name=" + encodeURIComponent(registration_doc["name"])
              fetch(registerExperimentURL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(registration_doc) })
              .then(checkHTTPResponse)
              .then(checkStatus)
              .catch((errmsg) => { errormsg(errmsg) })
            }
          })
      })      
    })
    .catch((error) => {console.log(error)});
  }