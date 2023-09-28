function patch_modal_defs(paramdefs) {
    paramdefs.forEach((paramdef) => {
        paramdef["param_type"] = _.get(paramdef, "param_type", "string"); 
        if(paramdef["param_type"] === "enum") {
            paramdef["options"] = paramdef["options"].map((optiondef) => { 
                if(_.isString(optiondef)) {
                    return { label: optiondef, value: optiondef }
                } else {
                    return optiondef;
                }
            })
        }
        paramdef["tab"] = _.get(paramdef, "tab", "Misc");
    })
}

let mdltypes = {
    "bool": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), checked = (currval === true) ? "checked" : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["param_name"]}"><label class="col-4 col-form-label">${label}</label><div class="col-8"><lgbk-checkbox ${checked} class="icon cp_value" ss_validate="bool"/></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    },
    "int": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["param_name"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><input type="number" class="form-control cp_value" value="${currval}" ss_validate="int"></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    }, 
    "float": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["param_name"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><input type="number" class="form-control cp_value" value="${currval}" ss_validate="float"></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    }, 
    "enum": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        let optionsstr = paramdef["options"].map((optiondef) => { 
            let selected = (optiondef["value"] === currval) ? "selected" : ""; 
            return `<option value="${optiondef["value"]}" ${selected}>${optiondef["label"]}</option>`
        }).join("");
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["param_name"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><select class="form-select ss_select cp_value" ss_validate="enum"><option></option>${optionsstr}</select></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    }, 
    "string": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["param_name"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><input type="text" class="form-control cp_value" value="${currval}" ss_validate="string"></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    },
    "custom": (parentElem, currkey, currval) => {
        let tempelem = document.createElement("div");
        tempelem.innerHTML = `<lgbk-custom-param class="row" name="${currkey}" value="${currval}"/>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
        lcp.setAddTemplate('<lgbk-custom-param class="row"/>');
    },
}

let elem2val = {
    "bool": (elem) => { return elem.querySelector(".cp_value").checked },
    "int": (elem) => { return  _.toInteger(elem.querySelector(".cp_value").value) },
    "float": (elem) => { return _.toNumber(elem.querySelector(".cp_value").value)},
    "enum": (elem) => { return elem.querySelector(".cp_value").value },
    "string": (elem) => { return elem.querySelector(".cp_value").value },
}

let checkForInvalidChars = (val) => {
    return !/^[\w/_-]+$/.test(_.trim(val));
}

export function modalshow(sampleid, allsamplesurl, onCompletion) {
    const baseUrl = lgbkabspath("");
    const modalUrl = baseUrl + "/static/html/mdls/samples/modal.html";
    const sampModalDefUrl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=samples";
    Promise.all([fetch(modalUrl), fetch(allsamplesurl), fetch(sampModalDefUrl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
    .then((vals) => {
        let [ mdltxt, sampresp, mdlparamsresp ] = vals, samples = sampresp["value"], mdlparams = mdlparamsresp["value"]["params"];
        patch_modal_defs(mdlparams); // Patch legacy modal definitions...
        let paramnm2def = _.keyBy(mdlparams, "param_name"), mdltabs = _.concat(_.uniq(_.map(mdlparams, "tab")), "Custom"), randid = Math.floor(Math.random() * (100000));
        let thesample = _.get(_.keyBy(samples, "_id"), sampleid, {"params": { }});    
        
        document.querySelector("#glbl_modals_go_here").innerHTML = mdltxt;
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");
        let tab2elem = { "Misc": formElem };
        if(mdltabs.length > 1 ) {
            let tempelem = document.createElement("div");
            let tabitems = mdltabs.map((tbnm) => { return `<li class="nav-item" role="presentation"><button class="nav-link" id="${tbnm}-${randid}" data-bs-toggle="tab" data-bs-target="#${tbnm}-${randid}-pane" type="button" role="tab">${tbnm}</button></li>` }).join("");
            let tabpanes = mdltabs.map((tbnm) => { return `<div class="tab-pane fade" id="${tbnm}-${randid}-pane" role="tabpanel" tabindex="0"></div>`}).join("");
            tempelem.innerHTML = `<ul class="nav nav-tabs" role="tablist" id="samp-${randid}">${tabitems}</ul><div class="tab-content">${tabpanes}</div>`;
            formElem.append(...tempelem.childNodes);
            mdltabs.forEach((tbnm) => { tab2elem[tbnm] = formElem.querySelector(`#${tbnm}-${randid}-pane`) })

            const firstTab = new bootstrap.Tab(formElem.querySelector(`#${mdltabs[0]}-${randid}`));
            firstTab.show();
        } else {
            tab2elem["Custom"] = formElem;
        }

        if(!_.isNil(sampleid)) {
            modalElem.querySelector('[data-name="name"] .cp_value').value = _.get(thesample, "name");
            modalElem.querySelector('[data-name="description"] .cp_value').value = _.get(thesample, "description");
        }
        
        _.each(mdlparams, (paramdef) => {
            mdltypes[paramdef["param_type"]](tab2elem[paramdef["tab"]], paramdef, _.get(thesample, "params." + paramdef["param_name"], _.get(paramdef, "default", "")));
        })

        let customkeys = _.difference(_.keys(_.get(thesample, "params", {})), _.map(mdlparams, "param_name"));
        console.log(customkeys);
        _.each(customkeys, (currkey) => { 
            let currval = _.get(thesample, "params."+currkey);
            mdltypes["custom"](tab2elem["Custom"], currkey, currval);
        })
        mdltypes["custom"](tab2elem["Custom"], "", "");

        const myModal = new bootstrap.Modal(modalElem);
        myModal.show();
        
        console.log(thesample);
        let showhidedependents = () => {
            let tabshowncount = _.fromPairs(_.map(mdltabs, (t) => { return [ t,  0 ] }));
            if(mdltabs.length > 1 ) { tabshowncount["Custom"] = 1 } 
            _.each(mdlparams, (dp) => {
                if(_.has(dp, "showwhen")) {
                    if(_.isMatch(thesample["params"], dp["showwhen"])) {
                        formElem.querySelector("[data-lgp-name="+ dp["param_name"] + "]").classList.remove("d-none");
                        tabshowncount[dp["tab"]] = tabshowncount[dp["tab"]] + 1;
                    } else {
                        formElem.querySelector("[data-lgp-name="+ dp["param_name"] + "]").classList.add("d-none");
                    }    
                } else {
                    tabshowncount[dp["tab"]] = tabshowncount[dp["tab"]] + 1;
                }
            })
            _.each(tabshowncount, (shwncnt, tbnm) => {
                if(shwncnt == 0) {
                    formElem.querySelector(`#${tbnm}-${randid}`).classList.add("d-none");
                    formElem.querySelector(`#${tbnm}-${randid}-pane`).classList.add("d-none");
                } else {
                    formElem.querySelector(`#${tbnm}-${randid}`).classList.remove("d-none");
                    formElem.querySelector(`#${tbnm}-${randid}-pane`).classList.remove("d-none");
                }
            })
        }
        showhidedependents();

        formElem.addEventListener("change", function(ev){
            let par = ev.target.closest("[data-lgp-name]");
            if(!_.isNil(par)) {
                let pname = par.getAttribute("data-lgp-name");
                let pval = elem2val[_.get(paramnm2def, pname+".param_type", "string")](par);
                console.log("Parameter " + pname + " changed to " + pval);
                _.set(thesample, "params."+pname, pval);
                showhidedependents();
            }
        })

        modalElem.querySelector(".add_sample").addEventListener("click", (event) => {
            event.preventDefault();
            let errormsg = (msg) => { modalElem.querySelector(".errormsg").innerHTML = msg; modalElem.querySelector(".errormsg").classList.remove("d-none"); }
            modalElem.querySelector(".errormsg").innerHTML = "";
            let sampleName = _.trim(modalElem.querySelector('[data-name="name"] .cp_value').value);
            if(_.isEmpty(sampleName)) { errormsg("The sample name cannot be blank"); return; }
            if(checkForInvalidChars(sampleName)) {
                errormsg("Please restrict sample names to alphanumeric characters, dashes, slashes and underscores.")
                return;
            }
            let description = modalElem.querySelector('[data-name="description"] .cp_value').value;
            if(_.isEmpty(description)) { errormsg("The sample description cannot be blank"); return; }
            let newsample = {name: sampleName, description: description, params: {}};

            let validated = _.every(Array.from(modalElem.querySelectorAll('[data-lgp-name]')).map((elem) => {
                let attrname = elem.getAttribute("data-lgp-name"), paramdef = paramnm2def[attrname];
                if(_.isNil(paramdef)) return true;
                let val = elem2val[paramdef["param_type"]](elem);
                if(_.isNil(val) || val === "") {
                    if(_.get(paramdef, "required", false)) {
                        let label =_.get(paramdef, "label", paramdef["param_name"])
                        errormsg(`The attribute ${label} is a required attribute`);
                        if(mdltabs.length > 1 ) {
                            const theTab = new bootstrap.Tab(formElem.querySelector(`#${paramdef['tab']}-${randid}`));
                            theTab.show();
                        }
                        return false;
                    }
                } else {
                    _.set(newsample, "params." + attrname, val);
                }
                return true;
            }))
            
            if(!validated) return;
            validated = _.every(Array.from(modalElem.querySelectorAll('lgbk-custom-param')).map((elem) => { return elem.validate(errormsg) }))
            if(!validated) {
                const theTab = new bootstrap.Tab(formElem.querySelector(`#Custom-${randid}`));
                theTab.show();
                return;
            }

            _.each(Array.from(modalElem.querySelectorAll('lgbk-custom-param')).map((elem) => { return elem.mergeinto(newsample["params"])}));

            async function checkHTTPResponse(resp) {
                if(!resp.ok) {
                    let respdata = await resp.text(); 
                    return Promise.reject(new Error(resp.statusText + " --> " + respdata));
                }
                return resp.json();
            }

            function checkStatus(status) {
                console.log(status); 
                if(!_.get(status, "success", true)) {
                    return Promise.reject(new Error(_.get(status, "errormsg", "Server side error, please check the logs")));
                }; 
                myModal.hide(); 
                onCompletion(); 
                return true; 
            }

            console.log(newsample);
            if(_.isNil(sampleid)) {
                let addSampleURL = allsamplesurl;
                fetch(addSampleURL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newsample) })
                .then(checkHTTPResponse)
                .then(checkStatus)
                .catch((errmsg) => { errormsg(errmsg) })
            } else {
                newsample["_id"] = thesample["_id"];
                let updateSampleURL = allsamplesurl + thesample["_id"];
                fetch(updateSampleURL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(newsample) })
                .then(checkHTTPResponse)
                .then(checkStatus)
                .catch((errmsg) => { errormsg(errmsg) })
            }
        });
    })
}