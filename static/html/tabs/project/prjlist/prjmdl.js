function patch_modal_defs(paramdefs) {
    paramdefs.forEach((paramdef) => {
        paramdef["id"] = paramdef["param_name"].replaceAll(".", "_");
        paramdef["tabid"] = paramdef["tab"].replaceAll(" ", "_");
    })
}

export function modalshow(prjid, onCompletion) {
    const baseUrl = lgbkabspath("");
    const modalUrl = baseUrl + "/static/html/tabs/project/prjlist/prjmdl.html";
    const defsUrl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=sampprep";
    const allprojectsurl = baseUrl + "/lgbk/ws/projects/";
    const prjUrl = baseUrl + (_.isNil(prjid) ? "/lgbk/ws/empty" : "/lgbk/ws/projects/"+prjid);
    Promise.all([fetch(modalUrl), fetch(defsUrl), fetch(prjUrl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
    .then((vals) => {
        let [ mdltxt, mdldefsjs, projresp ] = vals;
        const mdlparams = mdldefsjs.value.params;
        patch_modal_defs(mdlparams);

        let theprj = projresp["value"];
        let mdltab2label = _.fromPairs(_.map(_.groupBy(mdlparams, "tabid"), (lst, mid) => { return [ mid, lst[0]["tab"] ]}));
        mdltab2label["Custom"] = "Custom";
        
        document.querySelector("#glbl_modals_go_here").innerHTML = mdltxt;
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");
        let errormsg = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none"); }

        modalElem.querySelector('[data-name="name"] .cp_value').value = _.get(theprj, "name", "");
        modalElem.querySelector('[data-name="description"] .cp_value').value = _.get(theprj, "description", "");        

        import(lgbkabspath("/static/html/mdls/common/mdlparams.js")).then((mod) => { 
            const { LgbkCustomModalParams } = mod;
            let mdlParamsJS = new LgbkCustomModalParams(mdlparams, errormsg);
            console.log(mdlParamsJS);
            mdlParamsJS.render(theprj);
    
            const myModal = new bootstrap.Modal(modalElem);
            myModal.show();
            
            modalElem.querySelector(".aded_project").addEventListener("click", (event) => {
                event.preventDefault();
                modalElem.querySelector(".errormsg").innerHTML = "";
                let newprj = { "params": {} };
                let name = modalElem.querySelector('[data-name="name"] .cp_value').value;
                if(_.isNil(name) || _.isEmpty(name)) {
                    errormsg("The project name cannot be a blank string");
                    return;
                }

                let description = modalElem.querySelector('[data-name="description"] .cp_value').value;
                if(_.isNil(description) || _.isEmpty(description)) {
                    errormsg("Please enter a description");
                    return;
                }

                newprj["name"] = name;
                newprj["description"] = description;

                if(!mdlParamsJS.validate(newprj)){
                    return;
                }
    
                mdlParamsJS.createOrUpdate(allprojectsurl, prjid, newprj, () => { myModal.hide(); onCompletion(); });
            })
        })
  })
}