export function getURAWIRegistration(modalElem, startDate, endDate, event) {
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