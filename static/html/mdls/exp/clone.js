let error_message = function(message) {
    document.querySelector("#glbl_modals_go_here .errormsg").innerText = message;
    document.querySelector("#glbl_modals_go_here .errormsg").classList.remove("d-none");
}  

let form2doc = function(formElem, startDate, endDate) {
    let registration_doc = {};
    registration_doc["name"] = _.trim(formElem.querySelector(".experiment_name").value);
    registration_doc["start_time"] = startDate.viewDate.toJSON();
    registration_doc["end_time"] = endDate.viewDate.toJSON();
    return registration_doc;
}

let checkRequiredFields = function(registration_doc, error_message) { 
    let requiredFailed = [
      ["name", "Experiment name cannot be blank."],
      ["start_time", "Please choose a valid start time."],
      ["end_time", "Please choose a valid end time."]
    ].every((v) => {
      let val = _.get(registration_doc, v[0], "");
      if(val === "") { error_message(v[1]); return false; }
      return true;
    })
    return requiredFailed;
}

let checkOtherValidations = function(src_experiment_name, registration_doc) { 
    if(src_experiment_name === registration_doc["name"]) {
        error_message("Experiment name cannot be the same as the original."); return false;
    }

    const nmre = /^[\w/_-]+$/;
    if(!nmre.test(registration_doc["name"])) {
      error_message("Please restrict experiment names to alphanumeric characters, dashes, slashes and underscores."); return false;
    }

    if(!moment(registration_doc["end_time"]).isAfter(moment(registration_doc["start_time"]))) {
      error_message("The end time should be after the start time."); return false;
    }
    return true;
}

let ignore_naming_convention_for_experiment_name = null;
let checkExperimentNamingConvention = function(registration_doc, site_naming_conventions) {
  const experiment_name = registration_doc["name"];
  if(_.has(site_naming_conventions, "experiment.name.validation_regex") && experiment_name !== ignore_naming_convention_for_experiment_name) {
    let exp_nam_regex = new RegExp(_.get(site_naming_conventions, "experiment.name.validation_regex"));
    if(!exp_nam_regex.test(experiment_name)) {
      error_message("The experiment name " + experiment_name + " does not match the naming convention for this site. You can override this by clicking on the Clone button once more.");
      ignore_naming_convention_for_experiment_name = experiment_name;
      return false;
    }
  }
  return true;
}

export function clone_experiment(src_experiment_name, onCompletion) {
    console.log("Cloning experiment " + src_experiment_name);
    Promise.all([fetch(lgbkabspath("/static/html/mdls/exp/clone.html")), fetch(lgbkabspath("/lgbk/naming_conventions"))])
    .then((resps) => { if(resps.some((x) => !x.ok)){  return Promise.reject(new Error())}; return Promise.all([resps[0].text(), resps[1].json()])})
    .then((vals) => {
        let [ tmpl, nmcresp ] = vals, site_naming_conventions = _.get(nmcresp, "value", {});
        Mustache.parse(tmpl);
        document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(tmpl, {src_experiment_name: src_experiment_name, name: src_experiment_name, cloning: true, clone_attrs: [{k: "Experimental Setup", v: "setup"}, {k: "Samples", v: "samples"}, {k: "Roles", v: "roles"}, {k: "Run Parameter Descriptions", v: "run_param_descriptions"}]})
        const modalElem = document.querySelector("#glbl_modals_go_here .modal"), formElem = modalElem.querySelector("form");
        const myModal = new bootstrap.Modal(modalElem);
        modalElem.addEventListener("hidden.bs.modal", function(){ document.querySelector("#glbl_modals_go_here").innerHTML = ""; });
        let startDate = new tempusDominus.TempusDominus(modalElem.querySelector(".start_time"), {defaultDate: moment().toDate(), display: {sideBySide: true} });
        let endDate = new tempusDominus.TempusDominus(modalElem.querySelector(".end_time"), {defaultDate: moment().add(7, "days").toDate(), display: {sideBySide: true} });
        
        modalElem.querySelector(".clone_btn").addEventListener("click", (event) => {
            event.preventDefault();
            let registration_doc = form2doc(formElem, startDate, endDate);
            const experiment_name = registration_doc["name"];

            if(!checkRequiredFields(registration_doc)) return;
            if(!checkOtherValidations(src_experiment_name, registration_doc)) return;
            if(!checkExperimentNamingConvention(registration_doc, site_naming_conventions)) return;

            formElem.querySelectorAll(".clone_attr:checked").forEach(((ck) => { registration_doc[ck.getAttribute("name")] = true; }))
            console.log(registration_doc);
            fetch(lgbkabspath(
                "/lgbk/ws/clone_experiment" + "?experiment_name=" + encodeURIComponent(experiment_name) + "&src_experiment_name=" + encodeURIComponent(src_experiment_name)), 
                { method: "POST", headers: { "Content-Type": "application/json" }, 
                body: JSON.stringify(registration_doc)
            }).then((resp) => {
                if(!resp.ok) { return Promise.reject(new Error(resp.statusText)) } 
                return resp.json();                            
            }).then((status) => { 
                console.log(status); 
                if(!_.get(status, "success", true)) {
                    return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
                }; 
                myModal.hide(); 
                if(!_.isNil(onCompletion)) { onCompletion(experiment_name); }
            })
            .catch((errmsg) => { error_message(errmsg) })
        });
        myModal.show();
    })
    .catch((error) => {console.log(error)});
  };
  