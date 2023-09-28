async function addeditproject(prjid) {
    const { modalshow } = await import(lgbkabspath("/static/html/tabs/project/prjlist/prjmdl.js"));
    modalshow(prjid);
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
            tempelem.innerHTML = `<div class="row"><span class="lbl col">${at.label}</span><span class="col-8">${val}</span></div>`;
            tab2elem[at["tab"]].appendChild(tempelem.firstChild);
        })
        let selectedmachine = _.get(prjinfo, "params.sampleinfo.sample_prep_machine", "Vitrobot");
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
                    <span class="col-1">${_.get(gib, "number")}</span>
                    <span class="col-1">${_.get(gib, "boxposition")}</span>
                    <span class="col-1">${_.get(gib, "blottime")}</span>
                    <span class="col-1">${_.get(gib, "blotforce")}</span>
                    <span class="col-1">${_.get(gib, "blotwait")}</span>
                    <span class="col-1">${_.get(gib, "blottotal")}</span>
                    <span class="col-1">${_.get(gib, "draintime")}</span>
                    <span class="col-3">${_.get(gib, "sample")}</span>
                    <span class="col-2"></span>
                </div>`;
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
    })
    async function loadAndShowModal(modalurl) {
        console.log("Loading modal using '" + modalurl + "'. This resolves to '" + import.meta.resolve(modalurl) + "'");
        const { modalshow } = await import(modalurl);
        modalshow(target, () => { tabshow(target) });
    }
    document.querySelector("#toolbar_for_tab").innerHTML = `<span class="tlbricn home px-2"><i class="fa-solid fa-home fa-lg" title="Go to the projects page"></i></span><span class="tlbricn editsampprep px-2"><i class="fa-solid fa-edit fa-lg" title="Edit the sample preparation information"></i></span>`;
    document.querySelector("#toolbar_for_tab .editsampprep").addEventListener("click", (ev) => { 
        addeditproject(prjid);
    })
    document.querySelector("#toolbar_for_tab .home").addEventListener("click", (ev) => { 
        window.location = "../";
    })
} 