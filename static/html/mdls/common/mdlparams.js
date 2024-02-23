// Functions for rendering modal parameters from a custom params definition file.
// We could make this a component; but for the first iteration we're making this a bunch of javascript functions
// render takes a JSON definition, renders and append to the form elem in the modal
// validate 
// createOrUpdate updates the document and makes a server side REST call
// The serverURL is the document colleciton endpoint. POST into the collection should create a new document with PUT into the collection/<id> updates an existing document.

let mdltypes = {
    "bool": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), checked = (currval === true) ? "checked" : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["id"]}"><label class="col-4 col-form-label">${label}</label><div class="col-8"><lgbk-checkbox ${checked} class="icon cp_value" ss_validate="bool"/></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    },
    "int": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["id"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><input type="number" class="form-control cp_value" value="${currval}" ss_validate="int"></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    }, 
    "float": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["id"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><input type="number" class="form-control cp_value" value="${currval}" ss_validate="float"></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    }, 
    "enum": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        let optionsstr = paramdef["options"].map((optiondef) => { 
            let selected = (optiondef["value"] === currval) ? "selected" : ""; 
            return `<option value="${optiondef["value"]}" ${selected}>${optiondef["label"]}</option>`
        }).join("");
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["id"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><select class="form-select ss_select cp_value" ss_validate="enum"><option></option>${optionsstr}</select></div></div>`;
        let lcp = tempelem.firstChild;
        parentElem.appendChild(lcp);
    }, 
    "string": (parentElem, paramdef, currval) => {
        let tempelem = document.createElement("div"), label =_.get(paramdef, "label", paramdef["param_name"]), required = _.get(paramdef, "required", false) ? '<span class="pl-1 text-danger lbl-req">*</span>' : "", tooltip = _.get(paramdef, "description", label);
        tempelem.innerHTML = `<div class="row" title="${tooltip}" data-lgp-name="${paramdef["id"]}"><label class="col-4 col-form-label">${label}${required}</label><div class="col-8"><input type="text" class="form-control cp_value" value="${currval}" ss_validate="string"></div></div>`;
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

function patch_modal_defs(paramdefs) {
    paramdefs.forEach((paramdef) => {
        paramdef["id"] = paramdef["param_name"].replaceAll(".", "_");
        paramdef["tabid"] = paramdef["tab"].replaceAll(" ", "_");
    })
}

export class LgbkCustomModalParams {
    constructor(mdlparams, errormsg) {
        this.mdlparams = mdlparams;
        patch_modal_defs(this.mdlparams);
        this.errormsg = errormsg;
        this.randid = Math.floor(Math.random() * (100000));
        this.paramnm2def = _.keyBy(this.mdlparams, "id");
        this.mdltabs = _.concat(_.uniq(_.map(this.mdlparams, "tabid")), "Custom");
        this.mdltab2label = _.fromPairs(_.map(_.groupBy(this.mdlparams, "tabid"), (lst, mid) => { return [ mid, lst[0]["tab"] ]}));
        this.mdltab2label["Custom"] = "Custom";
    }
    
    render(thedocument) {
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        const formElem = modalElem.querySelector("form");
        let tab2elem = { "Misc": formElem };
        if(this.mdltabs.length > 1 ) {
            let tempelem = document.createElement("div");
            let tabitems = this.mdltabs.map((tbnm) => { return `<li class="nav-item" role="presentation"><button class="nav-link" id="${tbnm}-${this.randid}" data-bs-toggle="tab" data-bs-target="#${tbnm}-${this.randid}-pane" type="button" role="tab">${this.mdltab2label[tbnm]}</button></li>` }).join("");
            let tabpanes = this.mdltabs.map((tbnm) => { return `<div class="tab-pane fade" id="${tbnm}-${this.randid}-pane" role="tabpanel" tabindex="0"></div>`}).join("");
            tempelem.innerHTML = `<ul class="nav nav-tabs" role="tablist" id="samp-${this.randid}">${tabitems}</ul><div class="tab-content">${tabpanes}</div>`;
            formElem.append(...tempelem.childNodes);
            this.mdltabs.forEach((tbnm) => { tab2elem[tbnm] = formElem.querySelector(`#${tbnm}-${this.randid}-pane`) })
    
            const firstTab = new bootstrap.Tab(formElem.querySelector(`#${this.mdltabs[0]}-${this.randid}`));
            firstTab.show();
        } else {
            tab2elem["Custom"] = formElem;
        }
    
        _.each(this.mdlparams, (paramdef) => {
            mdltypes[paramdef["param_type"]](tab2elem[paramdef["tabid"]], paramdef, _.get(thedocument, paramdef["param_name"], _.get(paramdef, "default", "")));
        })
    
        let customkeys = _.difference(_.keys(_.get(thedocument, "params", {})), _.map(this.mdlparams, "param_name"));
        console.log(customkeys);
        _.each(customkeys, (currkey) => { 
            let currval = _.get(thedocument, "params."+currkey);
            if(_.isObject(currval)) return;
            mdltypes["custom"](tab2elem["Custom"], currkey, currval);
        })
        mdltypes["custom"](tab2elem["Custom"], "", "");
        
        console.log(thedocument);
        let isDeepMatch = (obj, query) => { 
            return _.every(query, (value, key) => { 
                return _.get(obj, key) == value;
            })
        }
        let showhidedependents = () => {
            let tabshowncount = _.fromPairs(_.map(this.mdltabs, (t) => { return [ t,  0 ] }));
            if(this.mdltabs.length > 1 ) { tabshowncount["Custom"] = 1 } 
            _.each(this.mdlparams, (dp) => {
                if(_.has(dp, "showwhen")) {
                    if(isDeepMatch(thedocument, dp["showwhen"])) {
                        formElem.querySelector("[data-lgp-name="+ dp["id"] + "]").classList.remove("d-none");
                        tabshowncount[dp["tabid"]] = tabshowncount[dp["tabid"]] + 1;
                    } else {
                        formElem.querySelector("[data-lgp-name="+ dp["id"] + "]").classList.add("d-none");
                    }    
                } else {
                    tabshowncount[dp["tabid"]] = tabshowncount[dp["tabid"]] + 1;
                }
            })
            _.each(tabshowncount, (shwncnt, tbnm) => {
                if(shwncnt == 0) {
                    formElem.querySelector(`#${tbnm}-${this.randid}`).classList.add("d-none");
                    formElem.querySelector(`#${tbnm}-${this.randid}-pane`).classList.add("d-none");
                } else {
                    formElem.querySelector(`#${tbnm}-${this.randid}`).classList.remove("d-none");
                    formElem.querySelector(`#${tbnm}-${this.randid}-pane`).classList.remove("d-none");
                }
            })
        }
        showhidedependents();
    
        formElem.addEventListener("change", function(ev){
            let par = ev.target.closest("[data-lgp-name]");
            if(!_.isNil(par)) {
                let pname = par.getAttribute("data-lgp-name");
                let paramdef = this.paramnm2def[pname];
                let pval = elem2val[_.get(paramdef, "param_type", "string")](par);
                console.log("Parameter " + paramdef["param_name"] + " changed to " + pval);
                _.set(thedocument, paramdef["param_name"], pval);
                showhidedependents();
            }
        })
    }

    validate(thenewdocument) {
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        let validated = _.every(Array.from(modalElem.querySelectorAll('[data-lgp-name]')).map((elem) => {
            let attrname = elem.getAttribute("data-lgp-name"), paramdef = this.paramnm2def[attrname];
            if(_.isNil(paramdef)) return true;
            let val = elem2val[paramdef["param_type"]](elem);
            if(_.isNil(val) || val === "") {
                if(_.get(paramdef, "required", false)) {
                    let label =_.get(paramdef, "label", paramdef["param_name"])
                    this.errormsg(`The attribute ${label} is a required attribute`);
                    if(this.mdltabs.length > 1 ) {
                        const theTab = new bootstrap.Tab(formElem.querySelector(`#${paramdef['tab']}-${this.randid}`));
                        theTab.show();
                    }
                    return false;
                }
            } else {
                _.set(thenewdocument, paramdef["param_name"], val);
            }
            return true;
        }))
        
        if(!validated) return false;
        validated = _.every(Array.from(modalElem.querySelectorAll('lgbk-custom-param')).map((elem) => { return elem.validate(this.errormsg) }))
        if(!validated) {
            const theTab = new bootstrap.Tab(formElem.querySelector(`#Custom-${this.randid}`));
            theTab.show();
            return false;
        }
    
        _.each(Array.from(modalElem.querySelectorAll('lgbk-custom-param')).map((elem) => { return elem.mergeinto(thenewdocument["params"])}));
        return true;
    }

    createOrUpdate(serverURL, thedocumentid, thenewdocument, onCompletion) {
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
                return Promise.reject(new Error(_.get(status, "this.errormsg", "Server side error, please check the logs")));
            }; 
            onCompletion(); 
            return true; 
        }
    
        console.log(thenewdocument);
        if(_.isNil(thedocumentid)) {
            let createDocumentURL = serverURL;
            fetch(createDocumentURL, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(thenewdocument) })
            .then(checkHTTPResponse)
            .then(checkStatus)
            .catch((errmsg) => { this.errormsg(errmsg) })
        } else {
            thenewdocument["_id"] = thedocumentid;
            let updateDocumentURL = serverURL + thenewdocument["_id"];
            fetch(updateDocumentURL, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(thenewdocument) })
            .then(checkHTTPResponse)
            .then(checkStatus)
            .catch((errmsg) => { this.errormsg(errmsg) })
        }
    }
}
