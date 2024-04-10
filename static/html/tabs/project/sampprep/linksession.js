export function modalshow(gridid, onCompletion) {
    const baseUrl = lgbkabspath("");
    const sessurl = baseUrl + "/lgbk/ws/projects/"+prjid+"/sessions";
    const modalUrl = baseUrl + "/static/html/tabs/project/sampprep/linksession.html", experiments_url = baseUrl + "/lgbk/ws/experiments";
    Promise.all([fetch(modalUrl), fetch(experiments_url), fetch(sessurl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
    .then((vals) => {
        let [ mdltxt, expresp, currsessionsresp ] = vals, exps = _.map(expresp["value"], "name"), currsessions = _.map(currsessionsresp["value"], "name");
        let sesschoices = _.difference(exps, currsessions);
        document.querySelector("#glbl_modals_go_here").innerHTML = mdltxt;
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        modalElem.querySelector("#prj_available_sessions").innerHTML = _.join(_.map(sesschoices, (s) => { return `<option value="${s}"></option>`;}), "\n");
        const myModal = new bootstrap.Modal(modalElem);
        myModal.show();
        modalElem.querySelector(".add_session").addEventListener("click", (event) => {
            event.preventDefault();
            let errmsg = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none") }
            let clrerr = () => { modalElem.querySelector(".errormsg").innerHTML = ""; modalElem.querySelector(".errormsg").classList.add("d-none"); modalElem.querySelector(".session_name").classList.remove("is-invalid"); }
            clrerr();
            let selectedSession = modalElem.querySelector(".session_name").value;
            if(!_.includes(sesschoices, selectedSession)) {
                modalElem.querySelector(".session_name").classList.add("is-invalid");
                return;
            }
            let addSessionURL = baseUrl + "/lgbk/ws/projects/"+prjid+"/grids/" + gridid + "/linksession?experiment_name="+selectedSession;
            fetch(addSessionURL)
            .then((resp) => { if(!resp.ok) { return Promise.reject(new Error("Server side error, please check the logs"))}  return resp.json()})
            .then((status) => { 
                console.log(status); 
                if(!_.get(status, "success", true)) {
                    return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
                }; 
                myModal.hide(); 
                onCompletion(); 
            })
            .catch((err) => { errmsg(err) })            
        });
    })
}
