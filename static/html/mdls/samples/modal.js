import { patch_modal_defs } from "./fns.js";

export function modalshow(sampleid, allsamplesurl, onCompletion) {
    const baseUrl = lgbkabspath("");
    const modalUrl = baseUrl + "/static/html/mdls/samples/modal.html";
    const defsUrl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=samples";
    const expinfoUrl = baseUrl + `/lgbk/${experiment_name}/ws/info`;
    Promise.all([fetch(modalUrl), fetch(allsamplesurl), fetch(defsUrl), fetch(expinfoUrl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json(), resps[3].json()])})
    .then((vals) => {
        let [ mdltxt, sampresp, mdlparamsresp, expinforesp ] = vals, samples = sampresp["value"], mdlparams = mdlparamsresp["value"]["params"], expinfo = expinforesp["value"];
        patch_modal_defs(mdlparams); // Patch legacy modal definitions...
        let paramnm2def = _.keyBy(mdlparams, "param_name"), mdltabs = _.concat(_.uniq(_.map(mdlparams, "tab")), "Custom"), randid = Math.floor(Math.random() * (100000));
        let thesample = _.get(_.keyBy(samples, "_id"), sampleid, {"params": { }});
        thesample.experiment = expinfo;
        
        document.querySelector("#glbl_modals_go_here").innerHTML = mdltxt;

        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");        
        let errormsg = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none"); }

        let clipBoardText = window.localStorage.getItem("explgbk.clipboard");
        if(!_.isNil(clipBoardText)) {
            let sampleDefnFromClipboard = _.pick(JSON.parse(clipBoardText), ["name", "description", "params"]);
            console.log(sampleDefnFromClipboard);
            _.merge(thesample, sampleDefnFromClipboard);
            console.log(thesample);
            window.localStorage.removeItem("explgbk.clipboard");
            errormsg("<b>Applying sample definition from the local storage for this browser. The clipboard has been cleared</b>");
        }

        modalElem.querySelector('[data-name="name"] .cp_value').value = _.get(thesample, "name", "");
        modalElem.querySelector('[data-name="description"] .cp_value').value = _.get(thesample, "description", "");        

        import(lgbkabspath("/static/html/mdls/common/mdlparams.js")).then((mod) => { 
            const { LgbkCustomModalParams } = mod;
            let mdlParamsJS = new LgbkCustomModalParams(mdlparams, errormsg);
            console.log(mdlParamsJS);
            mdlParamsJS.render(thesample);
    
            const myModal = new bootstrap.Modal(modalElem);
            myModal.show();
            
            modalElem.querySelector(".aded_sample").addEventListener("click", (event) => {
                event.preventDefault();
                modalElem.querySelector(".errormsg").innerHTML = "";
                let newsample = {};
                let name = modalElem.querySelector('[data-name="name"] .cp_value').value;
                if(_.isNil(name) || _.isEmpty(name)) {
                    errormsg("The sample name cannot be a blank string");
                    return;
                }

                let description = modalElem.querySelector('[data-name="description"] .cp_value').value;
                if(_.isNil(description) || _.isEmpty(description)) {
                    errormsg("Please enter a description");
                    return;
                }

                newsample["name"] = name;
                newsample["description"] = description;

                if(!mdlParamsJS.validate(newsample)){
                    return;
                }
    
                mdlParamsJS.createOrUpdate(allsamplesurl, sampleid, newsample, () => { myModal.hide(); onCompletion(); });
            })
        })
    })
}