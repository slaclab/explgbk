let setUpSampleChangeListener = function() {
    document.querySelector(".tab_title_bar.lgbk_socketio").addEventListener("samples", function(event){
        let sampleData = event.detail;
        if(_.get(sampleData, "CRUD", "") == "Make_Current") {
            current_sample_at_DAQ = _.get(sampleData, "value.name");
            setCurrentUISample();
            document.querySelectorAll(".tabcontainer").forEach((t) => { t.dispatchEvent(new Event("lg.DAQSampleChanged"))})
        }
    });
  }

let showPrivilegedActions = function() {
    _.each(privileges, function(v, k){
        if(v) {
            document.querySelectorAll("#myNavbar " + ".priv_"+k).forEach((x) => { x.classList.remove("d-none")});
            document.querySelectorAll("#myTabContainer " + ".priv_"+k).forEach((x) => { x.classList.remove("d-none")});
        }
    })
}

let setupHelp = function() { 
    document.querySelector("#lgbk_body span.help").addEventListener("click", function(){
        let hsh = window.location.hash, hlpurl = "../help";
        if(!_.isNil(hsh)) { hlpurl = hlpurl + hsh; }
        window.open(hlpurl, "_blank");
    })
}

let setupTimezoneBtn = function() {
    if(sessionStorage.getItem("use_local_timezone") != null && sessionStorage.getItem("use_local_timezone")) {
        console.log("Using the browser's locale timezone as the elog timezone");
        window.elog_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY")}};
        window.elog_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).format("MMM/D/YYYY HH:mm:ss")}};
    } else {
        console.log("Using PDT as the elog timezone");
        window.elog_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(elog_timezone).format("MMM/D/YYYY")}};
        window.elog_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(elog_timezone).format("MMM/D/YYYY HH:mm:ss")}};            
    }


    document.querySelector("#lgbk_body span.timezone").addEventListener("click", function(event){
        if(sessionStorage.getItem("use_local_timezone") != null && sessionStorage.getItem("use_local_timezone")) {
            sessionStorage.removeItem("use_local_timezone");
        } else {
            sessionStorage.setItem("use_local_timezone", true);
        }
        window.location.reload();
    })
}

let sessionTimeoutChecks = function() {
    if(auth_expiration_time > 1000000000) {
        var msToSessionTimeout = moment.unix(auth_expiration_time).diff(moment());
        console.log("Session times out in " + msToSessionTimeout + "(ms)");
        document.querySelector(".session_items").setAttribute("title", "Your session will expire at " + moment.unix(auth_expiration_time).format("dddd, MMMM Do YYYY, h:mm:ss a"));
        var on_session_timeout = function() {
            let lgt = function() { window.location.href="../logout" };
            error_message("Your session is about to or has already timed out. Please logout and log back in to continue your work.");
            setTimeout(lgt, 21000);
        }
        if(msToSessionTimeout > 30000) {
            setTimeout(on_session_timeout, msToSessionTimeout - 30000);
        } else {
            on_session_timeout();
        }
    }
}

let setupZoom = function() {
    fetch("ws/info")
    .then((resp) => { return resp.json() })
    .then((info) => {
        let zoom_meeting_url = _.get(info, "value.params.zoom_meeting_url", "");
        let zoom_meeting_id = _.get(info, "value.params.zoom_meeting_id", "");
        let zoom_meeting_pwd = _.get(info, "value.params.zoom_meeting_pwd", "");
        let zoom_meeting_can_edit = _.get(privileges, "manage_groups", false);

        let tempelem = document.createElement("div");
        tempelem.innerHTML = `<li class="px-2"><span class="zoom" title="Zoom meeting for this experiment"><a href="#"><i class="fa-solid fa-phone-alt fa-lg"></i> Zoom</a></span></li>`;
        document.querySelector("#myNavbar .help").parentElement.before(tempelem.firstChild);
        let zmr = document.querySelector("#myNavbar .zoom");
        zmr.addEventListener("click", function(){
            fetch("../../static/html/ms/zoom_meeting.html")
            .then((resp) => { return resp.text()})
            .then((tmpl) => {
                Mustache.parse(tmpl);
                document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(tmpl, { experiment_name: experiment_name, zoom_meeting_url: zoom_meeting_url, zoom_meeting_id: zoom_meeting_id, zoom_meeting_pwd: zoom_meeting_pwd, zoom_meeting_can_edit: zoom_meeting_can_edit });
                let modalElem = document.querySelector("#glbl_modals_go_here .modal");
                const myModal = new bootstrap.Modal(modalElem);
                let error_message = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none"); }
                modalElem.querySelector(".zoom_edit")?.addEventListener("click", (event) => {
                    if(event.target.innerText == "Save") {
                        zoom_meeting_url = modalElem.querySelector(".zoom_meeting_details_edit input.zoom_meeting_url").value;
                        zoom_meeting_id = modalElem.querySelector(".zoom_meeting_details_edit input.zoom_meeting_id").value;
                        zoom_meeting_pwd = modalElem.querySelector(".zoom_meeting_details_edit input.zoom_meeting_pwd").value;
                        if(_.isEmpty(zoom_meeting_url) || _.isEmpty(zoom_meeting_id)) {
                            error_message("Please enter a valid meeting URL and id.");
                            return
                        }
                        fetch("ws/add_update_experiment_params", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({"zoom_meeting_url": zoom_meeting_url, "zoom_meeting_id": zoom_meeting_id, "zoom_meeting_pwd": zoom_meeting_pwd}) })
                        .then((resp) => {
                            if(!resp.ok) { return Promise.reject(new Error(resp.statusText)) } 
                            return resp.json();                            
                        })
                        .then((status) => { 
                            console.log(status); 
                            if(!_.get(status, "success", true)) {
                                return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
                            }; 
                            myModal.hide(); 
                        })
                        .catch((errmsg) => { error_message(errmsg) })
                    } else {
                        modalElem.querySelector(".zoom_meeting_details").classList.add("d-none");
                        modalElem.querySelector(".zoom_meeting_details_edit").classList.remove("d-none");
                        modalElem.querySelector(".zoom_edit").innerText = "Save";
                    }
                })
                modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
                myModal.show();
              })
          })

    })
}

let setupStandbyButton = function(c_active) {
    let stby_tmpl = `<span class="standby" data-instrument="{{ instrument }}" data-station="{{ station }}" title="End this experiment and put this instrument/station in standby mode."><i class="fa-solid fa-power-off fa-lg"></i></span>`; Mustache.parse(stby_tmpl);
    let expactinfo = _.find(c_active, ["name", experiment_name]);
    let tempelem = document.createElement("div");
    tempelem.innerHTML = Mustache.render(stby_tmpl, expactinfo);
    document.querySelector("#myNavbar .currently_active").append(tempelem.firstChild);
    let standbyelem = document.querySelector("#myNavbar .standby");
    standbyelem.addEventListener("click", (event) => { 
        fetch("../../static/html/ms/generic_yes_no.html")
        .then((resp) => { return resp.text() })
        .then((d0) => {
            let msg = `Please confirm that you want to put this instrument {{ instrument }}/station {{ station }} on standby`;
            Mustache.parse(msg);
            document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(d0, {"title": "Please confirm", "message": Mustache.render(msg, expactinfo)});
            let stbyModalElem = document.querySelector("#glbl_modals_go_here .modal");
            const myModal = new bootstrap.Modal(stbyModalElem);
            let error_message = (msg) => { stbyModalElem.querySelector(".errormsg").innerHTML = msg; stbyModalElem.querySelector(".errormsg").classList.remove("d-none"); }
            let instrument_standby_from_within_experiment = (event) => {
                let instr = expactinfo["instrument"];
                let station = expactinfo["station"];
                console.log("Putting " + instr + "/" + station + " into standby/maintenance mode.");
                fetch("../ws/instrument_standby", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({"instrument": instr, "station": station}) })
                .then((resp) => {
                    if(!resp.ok) { return Promise.reject(new Error(resp.statusText)) } 
                    return resp.json();                            
                }).then((status) => { 
                    console.log(status); 
                    if(!_.get(status, "success", true)) {
                        return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
                    }; 
                    myModal.hide(); 
                    window.location.reload();
                })
                .catch((errmsg) => { error_message(errmsg) })
            }
            stbyModalElem.querySelector(".yesbutton").removeAttribute("data-bs-dismiss");
            stbyModalElem.querySelector(".yesbutton").addEventListener("click", instrument_standby_from_within_experiment);
            myModal.show();        
        })
    })    
}

let setupSwitchWithinExperiment = function() {
    let switch_tmpl = `<li><button class="navbar_icon_btn switch" title="Make this experiment the current experiment on an instrument"><span class="btntext">Switch</span><i class="fa-solid fa-exchange-alt fa-lg" aria-hidden="true"></i></button></li>`;
    Mustache.parse(switch_tmpl);
    let tempelem = document.createElement("div");
    tempelem.innerHTML = Mustache.render(switch_tmpl, {});
    document.querySelector("#myNavbar .session_items").before(tempelem.firstChild);
    document.querySelector("#myNavbar .switch").addEventListener("click", (event) => {
        Promise.all([fetch(lgbkabspath("/static/html/ms/switch_within_experiment.html")), fetch(lgbkabspath("/lgbk//ws/instrument_station_list")), fetch(lgbkabspath("/lgbk/ws/activeexperiments"))])
        .then((resps) => { if(resps.some((x) => !x.ok)){  return Promise.reject(new Error())}; return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
        .then((vals) => {
            let [ mdltmpl, islr, acr ] = vals;
            let stations_by_ins = _.groupBy(islr.value, "instrument"), c_active = acr.value;
            let msobj = {experiment: experiment_name, instrument: instrument_name};
            if(_.get(stations_by_ins, instrument_name, []).length > 1) {
                msobj["stations"] = _.get(stations_by_ins, instrument_name);
                _.each(msobj["stations"], function(is){ is["currently_used_by"] = _.get(_.find(c_active, function(x){ return x["instrument"] === is["instrument"] && x["station"] === is["station"]}), "name", "") })
            } else {
                msobj["currently_used_by"] = _.get(_.find(c_active, function(x){ return x["instrument"] === instrument_name && x["station"] === 0}), "name", "")
            }
            console.log(msobj);
            document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(mdltmpl, msobj);
            let modalElem = document.querySelector("#glbl_modals_go_here .modal"), formElem = modalElem.querySelector("form");
            const myModal = new bootstrap.Modal(modalElem);
            let error_message = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none"); }            
            let stationToSwitch = "0";
            if(_.get(stations_by_ins, instrument_name, []).length > 1) {
                formElem.querySelector("table").parentElement.classList.remove("d-none");
                formElem.querySelector('table tr[data-station="0"]').classList.add("rowselect");
                stationToSwitch = "0";
                formElem.querySelectorAll(".station").forEach((st) => { 
                    st.addEventListener("click", (event) => {
                        let clk = event.target;
                        clk.closest("table").querySelectorAll(".rowselect").forEach((tr) => { tr.classList.remove("rowselect")} )
                        clk.closest("tr").classList.add("rowselect");
                        stationToSwitch = clk.closest("tr").getAttribute(["data-station"]);
                    })
                })
            }
            modalElem.querySelector(".activate_exp").addEventListener("click", (event) => { 
                let station_data = {instrument: instrument_name, station: stationToSwitch, experiment_name: experiment_name };
                console.log(`Activating ${station_data.experiment_name} on instrument ${station_data.instrument} station ${station_data.station}`);
                fetch("../ws/switch_experiment", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(station_data) })
                .then((resp) => {
                    if(!resp.ok) { return Promise.reject(new Error(resp.statusText)) } 
                    return resp.json();                            
                }).then((status) => { 
                    console.log(status); 
                    if(!_.get(status, "success", true)) {
                        return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
                    }; 
                    myModal.hide(); 
                    window.location.reload();
                })
                .catch((errmsg) => { error_message(errmsg) })
            })
            modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
            myModal.show();
        })
    })
}

let setupCloneButton = function() {
    let clone_tmpl = `<li class="clone_tb pe-2"><span class="exp_clone" title="Clone this experiment"><i class="fa-solid fa-clone fa-lg"></i></span></li>`;
    Mustache.parse(clone_tmpl);
    let tempelem = document.createElement("div");
    tempelem.innerHTML = Mustache.render(clone_tmpl, {src_experiment_name: experiment_name});
    document.querySelector("#myNavbar .session_items").before(tempelem.firstChild);
    
    async function loadModal(taburl, target) {
        const { clone_experiment } = await import(lgbkabspath("/static/html/mdls/exp/clone.js"));
        clone_experiment(experiment_name);
    }

    document.querySelector("#myNavbar .exp_clone").addEventListener("click", (event => { 
        loadModal();
    }));
}

let setupCreateSwitchExperimentButtons = function() {
    fetch("../ws/activeexperiments")
    .then((resp) => { return resp.json() })
    .then((d1) => {
        let c_active = d1.value;
        if(_.includes(_.map(c_active, "name"), experiment_name)) {
            let expactinfo = _.find(c_active, ["name", experiment_name]);
            console.log(expactinfo);
            let curr_active_tmpl = `<li title="This experiment is currently active on this instrument {{instrument}}/station {{station}}"><span class="currently_active"><span class="instrument">{{instrument}}</span>/<span class="station">{{station}}</span></span></li>`;
            Mustache.parse(curr_active_tmpl);
            let tempelem = document.createElement("div");
            tempelem.innerHTML = Mustache.render(curr_active_tmpl, expactinfo);
            document.querySelector("#myNavbar .session_items").before(tempelem.firstChild);
        }

        if(_.get(privileges, "switch", false) && _.get(privileges, "experiment_create", false)) {
            if(_.includes(_.map(c_active, "name"), experiment_name)) {
                setupStandbyButton(c_active);
            } else {
                setupSwitchWithinExperiment();
            }
            setupCloneButton();
        }
    })
}

export function miscSetup() {
    setUpSampleChangeListener();
    showPrivilegedActions();
    setupHelp();
    setupTimezoneBtn();
    setupZoom();
    sessionTimeoutChecks();
    setupCreateSwitchExperimentButtons();
}