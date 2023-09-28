export function tabshow(target) {
    const baseUrl = target.getAttribute("data-lg-url").split("/static")[0];
    const sessurl = baseUrl + "/lgbk/ws/projects/"+prjid+"/sessions";
    const templateurl = baseUrl + "/static/html/tabs/project/sessions/sessions.html";
    console.log("Inside tab show for sessions " + sessurl);
    Promise.all([fetch(new Request(sessurl)), fetch(new Request(templateurl))])
    .then((resps) => {
        return Promise.all([resps[0].json(), resps[1].text()]);
    })
    .then((vals) => {
        let [ sessions, tmpl ]= vals;
        let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
        trgt.innerHTML=tmpl;
        const tbody = trgt.querySelector("tbody");
        const template = trgt.querySelector("#projectsession");
        _.each(sessions["value"], (session) => { 
            const clone = template.content.cloneNode(true);
            let td = clone.querySelectorAll("td");
            td[0].innerHTML = `<a href="${baseUrl}/lgbk/${session["name"]}/info" target="_blank">${session["name"]}</a>`;
            td[1].textContent = _.get(session, "aliquot", "N/A");
            td[2].textContent = _.get(session, "gridnum", "N/A");
            td[3].textContent = _.get(session, "expinfo.instrument", "N/A");
            td[4].textContent = _.get(session, "expinfo.run_count", "N/A");
            td[5].textContent = dayjs(_.get(session, "expinfo.last_run.begin_time")).format('MMM DD YYYY HH:mm:ss');
            tbody.appendChild(clone);
        })
    })
    async function loadAndShowModal(modalurl) {
        console.log("Loading modal using '" + modalurl + "'. This resolves to '" + import.meta.resolve(modalurl) + "'");
        const { modalshow } = await import(modalurl);
        modalshow(target, () => { tabshow(target) });
    }
    document.querySelector("#toolbar_for_tab").innerHTML = `<span class="tlbricn newsess px-2"><i class="fa-solid fa-plus fa-lg" title="Create a new session associated with this project"></i></span><span class="tlbricn incsess"><i class="fa-solid fa-square-plus fa-lg" title="Associate an existing session with this project"></i></span>`;
    document.querySelector("#toolbar_for_tab .incsess").addEventListener("click", (event) => {
        // Module specifier are resolved using the current module's URL as base.
        // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/import.meta/resolve
        loadAndShowModal(baseUrl + "/tabs/project/sessions/addsession.js");
    })
    document.querySelector("#toolbar_for_tab .newsess").addEventListener("click", (event) => {
        class Customizer {
            customize(modalElem, formElem, expInfo) {
                let customHTML = `<div class="row">
                    <div class="form-group col-4">
                        <label>Please specify the aliquot:</label>
                        <input type="text" class="form-control aliquot">
                    </div>
                    <div class="form-group col-4">
                        <label>Please specify the grid number:</label>
                        <input type="text" class="form-control gridnum">
                    </div>
                </div>`;
                let tempelem = document.createElement("div");
                tempelem.innerHTML = customHTML;
                let lcp = tempelem.firstChild;
                formElem.querySelector(".description").closest(".row").before(lcp);
            }
            validate(modalElem, formElem, registration_doc, error_message) {
                let aliquot = _.trim(formElem.querySelector(".aliquot").value);
                let gridnum = _.trim(formElem.querySelector(".gridnum").value);
                if(aliquot === "") { error_message("Please specify the aliquot for this session"); return false; }
                if(gridnum === "") { error_message("Please specify the grid number for this session"); return false; }
                return true;
            }
            
            onCompletion(myModal, formElem, registration_doc, error_message) {
                let addSessionURL = baseUrl + "/lgbk/ws/projects/"+prjid+"/sessions/";
                let aliquot = _.trim(formElem.querySelector(".aliquot").value);
                let gridnum = _.trim(formElem.querySelector(".gridnum").value);
                let selectedSession = registration_doc["name"];
                let sessionDetails = { "name":  selectedSession, "aliquot": aliquot, "gridnum": gridnum}
                fetch(addSessionURL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sessionDetails) })
                .then((resp) => { if(!resp.ok) { error_message("Server side error"); throw Error() }  return resp.json()})
                .then((status) => {
                    console.log(status);
                    myModal.hide(); 
                    tabshow(target);
                })
            }
        }
        let customizer = new Customizer();
        async function loadAndShowRegistrationModal(modalurl) {
            console.log("Loading modal using '" + modalurl + "'. This resolves to '" + import.meta.resolve(modalurl) + "'");
            const { lgbk_create_edit_exp } = await import(modalurl);
            lgbk_create_edit_exp({ leader_account: logged_in_user, contact_info: _.get(logged_in_user_details, "gecos", logged_in_user) + "( " + logged_in_user + "@slac.stanford.edu )", start_time : moment(), end_time : moment().add(2, 'days') }, customizer);
        }
        loadAndShowRegistrationModal(baseUrl + "/mdls/exp/reg.js");
    })

} 