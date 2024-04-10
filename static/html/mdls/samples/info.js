import { patch_modal_defs } from "./fns.js";

function sample2Clipboard(sampleDefinition) {
    // Only local storage seems to work across all browsers.
    window.localStorage.setItem("explgbk.clipboard", JSON.stringify(sampleDefinition));
    showToast("Copied sample definition into the local storage for this browser", 5.00, "text-bg-info");
}

export function modalshow(sampleid, allsamplesurl, onCompletion) {
    const baseUrl = lgbkabspath("");
    const modalUrl = baseUrl + "/static/html/mdls/samples/info.html";
    const sampModalDefUrl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=samples";
    Promise.all([fetch(modalUrl), fetch(allsamplesurl), fetch(sampModalDefUrl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
    .then((vals) => {
        let [ mdltxt, sampresp, mdlparamsresp ] = vals, samples = sampresp["value"], mdlparams = mdlparamsresp["value"]["params"];
        mdlparams.unshift({"param_name": "name", "label": "Name", "tab": "Info"}, {"param_name": "description", "label": "Description", "tab": "Info"});
        patch_modal_defs(mdlparams); // Patch legacy modal definitions...
        let mdltabs = _.concat(_.uniq(_.map(mdlparams, "tab")), "Custom");
        let paramsbytab = _.groupBy(mdlparams, "tab");
        let thesample = _.get(_.keyBy(samples, "_id"), sampleid, {"params": { }});
        let customkeys = _.filter(_.difference(deepKeys(thesample), _.map(mdlparams, "param_name")), (p) => _.startsWith(p, "params."));
        paramsbytab["Custom"] = _.map(customkeys, (k) => { return {"param_name": k, "label": _.replace(k, "params.", ""), "tab": "Custom"}})

        document.querySelector("#glbl_modals_go_here").innerHTML = mdltxt;
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");
        _.each(mdltabs, (tab) => {
            let tempelem = document.createElement("div");
            tempelem.innerHTML = `<div class="card"><div class="card-body"><h5 class="card-title">${tab}</h5><div class="card-text tabcontent"></div></div></div>`;
            _.each(paramsbytab[tab], (tc) => { 
                let tcelem = document.createElement("div");
                tcelem.innerHTML = `<div class="row"><label class="col-5">${tc.label}</label><span class="col-7">${_.get(thesample, tc["param_name"], "")}</span></div>`
                tempelem.querySelector(".tabcontent").appendChild(tcelem.firstChild);
            })
            formElem.appendChild(tempelem.firstChild);
        })

        modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
        modalElem.querySelector(".copy-btn").addEventListener("click", (ev) => { 
            console.log("Copying sample definition to the clipboard");
            sample2Clipboard(thesample);
        })
        const myModal = new bootstrap.Modal(modalElem);
        myModal.show();
    })
}

