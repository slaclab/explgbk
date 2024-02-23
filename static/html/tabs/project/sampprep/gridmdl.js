let checkForInvalidChars = (val) => {
    return !/^[\w/_-]+$/.test(_.trim(val));
}

export function modalshow(gridid, onCompletion) {
    const baseUrl = lgbkabspath("");
    const modalUrl = baseUrl + "/static/html/tabs/project/sampprep/gridmdl.html";
    const defsUrl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=sampprepgrid";
    const gridUrl = baseUrl + (_.isNil(gridid) ? "/lgbk/ws/empty" : "/lgbk/ws/projects/"+prjid+"/grids/"+gridid);
    Promise.all([fetch(modalUrl), fetch(defsUrl), fetch(gridUrl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
    .then((vals) => {
        let [ mdltxt, mdldefsjs, gridresp ] = vals;
        const mdlparams = mdldefsjs.value.params;
        document.querySelector("#glbl_modals_go_here").innerHTML = mdltxt;
        let thegrid = gridresp.value;
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        let errormsg = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none"); }

        import(lgbkabspath("/static/html/mdls/common/mdlparams.js")).then((mod) => { 
            const { LgbkCustomModalParams } = mod;
            let mdlParamsJS = new LgbkCustomModalParams(mdlparams, errormsg);
            console.log(mdlParamsJS);
            mdlParamsJS.render(thegrid);
    
            const myModal = new bootstrap.Modal(modalElem);
            myModal.show();
            
            modalElem.querySelector(".aded_grid").addEventListener("click", (event) => {
                event.preventDefault();
                modalElem.querySelector(".errormsg").innerHTML = "";
                let newgrid = {};
                if(!mdlParamsJS.validate(newgrid)){
                    return;
                }
    
                mdlParamsJS.createOrUpdate(baseUrl + "/lgbk/ws/projects/"+prjid+"/grids/", gridid, newgrid, () => { myModal.hide(); onCompletion(); });
            })
        })
   })
}