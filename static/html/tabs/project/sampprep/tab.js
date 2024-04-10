async function addeditproject(prjid) {
    const { modalshow } = await import(lgbkabspath("/static/html/tabs/project/prjlist/prjmdl.js"));
    modalshow(prjid, () => { window.location.reload() });
}

async function addeditgrid(gridid) {
    const { modalshow } = await import(lgbkabspath("/static/html/tabs/project/sampprep/gridmdl.js"));
    modalshow(gridid, () => { window.location.reload() });
}

async function newsession(gridid) {
    const { lgbk_create_edit_exp } = await import(lgbkabspath("/static/html/mdls/exp/reg.js"));
    let theexp = { leader_account: logged_in_user, contact_info: _.get(logged_in_user_details, "gecos", logged_in_user) + "( " + logged_in_user + "@slac.stanford.edu )", start_time : moment(), end_time : moment().add(2, 'days')};
    lgbk_create_edit_exp(theexp, (created_exp) => { 
        console.log("Done with the create exp modal", created_exp); 
        let addSessionURL = lgbkabspath("/lgbk/ws/projects/"+prjid+"/grids/" + gridid + "/linksession?experiment_name="+created_exp["name"]);
        fetch(addSessionURL)
        .then((resp) => { if(!resp.ok) { return Promise.reject(new Error("Server side error, please check the logs"))}  return resp.json()})
        .then((status) => { 
            console.log(status); 
            if(!_.get(status, "success", true)) {
                return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
            }; 
            window.location.reload();
        })
        .catch((err) => { error_message(err) })
    });
}

async function linksession(gridid) {
    const { modalshow } = await import(lgbkabspath("/static/html/tabs/project/sampprep/linksession.js"));
    modalshow(gridid, () => { window.location.reload() });
}

export function tabshow(target) {
    const baseUrl = target.getAttribute("data-lg-url").split("/static")[0];
    const templateurl = baseUrl + "/static/html/tabs/project/sampprep/sampprep.html";
    const prjinfourl = baseUrl + "/lgbk/ws/projects/"+prjid;
    const prjattrsurl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=sampprep";
    const gridsurl = baseUrl + "/lgbk/ws/projects/"+prjid+"/grids";
    Promise.all([
        fetch(new Request(templateurl)),
        fetch(new Request(prjinfourl)), 
        fetch(new Request(prjattrsurl)), 
        fetch(new Request(gridsurl)), 
    ])
    .then((resps) => {
        return Promise.all([
            resps[0].text(),
            resps[1].json(), 
            resps[2].json(), 
            resps[3].json(), 
        ]);
    })
    .then((vals) => {
        let [ tmpl, prjinfo, prjattrs, grids ] = vals;
        prjinfo = prjinfo.value; prjattrs = prjattrs.value.params; grids = grids.value;

        let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
        trgt.innerHTML=tmpl;
        const mdltabs = _.uniq(_.map(prjattrs, "tab"));
        const tab2elem = _.fromPairs(_.map(mdltabs, (tb) => { return [tb, document.querySelector("[data-lgbk-for-tab='"+tb+"']")] }))
        _.each(prjattrs, (at) => {
            let val = _.get(prjinfo, "params." +at["param_name"], "");
            let tempelem = document.createElement("div");
            tempelem.innerHTML = `<div class="row"><span class="lbl col">${at.label}</span><span class="col-6">${val}</span></div>`;
            tab2elem[at["tab"]].appendChild(tempelem.firstChild);
        })
        let selectedmachine = _.get(prjinfo, "params.sampleinfo.sample_prep_machine", "Vitrobot Mark 4");
        document.querySelector("[data-lgbk-for-tab='"+ selectedmachine +"']").closest(".box").classList.remove("d-none");
        document.querySelector("#prjcomment textarea").innerHTML = _.get(prjinfo, "comments", "");
        document.querySelector("#prjcomment textarea").addEventListener("change", (ev) => {
            const newcomment = ev.target.value;
            if(newcomment !== _.get(prjinfo, "comments")) {
                let updateProjectURL = baseUrl + "/lgbk/ws/projects/" + prjid;
                fetch(updateProjectURL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({"comments": newcomment}) })
                .then((resp) => {
                    if(resp.ok) {
                        success_message("Updated comment");
                    } else {
                        error_message("Error updating comment; please check the server logs");
                    }
                })
            }
        })

        let griddetails = document.querySelector("div.griddetails");
        let gridboxes = _.uniq(_.map(grids, "box"));
        let box2grids = _.groupBy(grids, "box");
        _.each(gridboxes, (gb) => {
            let gridsinbox = box2grids[gb];
            gridsinbox = _.concat(gridsinbox, _.times(4-gridsinbox.length, _.constant({})));
            _.each(gridsinbox, (gib) => {
                let tempElem = document.createElement("div");
                tempElem.innerHTML = `<div class="row grid">
                    <span class="col-1">
                        <span class="actnicn editgrid"><i class="fa-solid fa-edit fa-lg" title="Edit this grid"></i></span>
                        <span class="actnicn newsess"><i class="fa-solid fa-plus fa-lg" title="Create a new session and associate with this project"></i></span>
                        <span class="actnicn incsess"><i class="fa-solid fa-square-plus fa-lg" title="Associate an existing session with this project"></i></span>
                    </span>
                    <span class="col-1">${_.get(gib, "number", "")}</span>
                    <span class="col-1">${_.get(gib, "boxposition", "")}</span>
                    <span class="col-1">${_.get(gib, "blottime", "")}</span>
                    <span class="col-1">${_.get(gib, "blotforce", "")}</span>
                    <span class="col-1">${_.get(gib, "blotwait", "")}</span>
                    <span class="col-1">${_.get(gib, "blottotal", "")}</span>
                    <span class="col-1">${_.get(gib, "draintime", "")}</span>
                    <span class="col-2">${_.get(gib, "sample", "")}</span>
                    <span class="col-2"><a href="../../${_.get(gib, "exp_name", "")}/info" target="_blank">${_.get(gib, "exp_name", "")}</a></span>
                </div>`;
                tempElem.querySelector(".editgrid").addEventListener("click", (ev) => { 
                    addeditgrid(gib["_id"]);
                })
                tempElem.querySelector(".newsess").addEventListener("click", (ev) => { 
                    newsession(gib["_id"]);
                })
                tempElem.querySelector(".incsess").addEventListener("click", (ev) => { 
                    linksession(gib["_id"]);
                })
                griddetails.appendChild(tempElem.firstChild);    
            })
            let tempElem = document.createElement("div");
            tempElem.innerHTML = `<div class="row gbsub text-start">
                <span class="col-1 sblbl">Grid Box</span>
                <span class="col-2">${_.get(gridsinbox, "0.box")}</span>
                <span class="col-2 sblbl">Grid Container</span>
                <span class="col-2">${_.get(gridsinbox, "0.container")}</span>
                <span class="col-1 sblbl">Grid Type</span>
                <span class="col-4">${_.get(gridsinbox, "0.gridtype")}</span>
            </div>`;
            griddetails.appendChild(tempElem.firstChild);
        })
        document.querySelector("#sampprep_tab .griddetails .newgrid").addEventListener("click", (ev) => { 
            addeditgrid();
        })    
    })
    document.querySelector("#toolbar_for_tab").innerHTML = `<span class="tlbricn home px-2"><i class="fa-solid fa-home fa-lg" title="Go to the projects page"></i></span><span class="tlbricn editsampprep px-2"><i class="fa-solid fa-edit fa-lg" title="Edit the sample preparation information"></i></span>`;
    document.querySelector("#toolbar_for_tab .editsampprep").addEventListener("click", (ev) => { 
        addeditproject(prjid);
    })
    document.querySelector("#toolbar_for_tab .home").addEventListener("click", (ev) => { 
        window.location = "../";
    })
} 