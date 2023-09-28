export function modalshow(sampleid, allsamplesurl, onCompletion) {
    const baseUrl = lgbkabspath("");
    const modalUrl = baseUrl + "/static/html/mdls/samples/info.html";
    const sampModalDefUrl = baseUrl + "/lgbk/get_modal_param_definitions?modal_type=samples";
    Promise.all([fetch(modalUrl), fetch(allsamplesurl), fetch(sampModalDefUrl)])
    .then((resps) => { return Promise.all([resps[0].text(), resps[1].json(), resps[2].json()])})
    .then((vals) => {
        let [ tmpl, sampresp, mdlparamsresp ] = vals, samples = sampresp["value"], mdlparams = mdlparamsresp["value"]["params"];
        let pdd = _.keyBy(mdlparams, "param_name"), kvs = [];
        let thesample = _.get(_.keyBy(samples, "_id"), sampleid, {"params": { }});            
        _.each(pdd, function(v,k,o){
          let prep_cp = function(p) {
              p["is_"+ _.get(p, "param_type", "string")] = true;
              _.defaults(p, {"label": _.get(p, "param_name")});
              _.defaults(p, {"description": _.get(p, "description")});
              if(_.get(p, "param_type", "string") == "bool") {p["is_checked"] = _.get(thesample, "params." + p["param_name"], false)}
              if(_.has(p, "options")){ _.each(p["options"], function(x){ if(_.get(x, "value", x) == _.get(p, "current_val")) { p["current_val"] = _.get(x, "label", x) }})}
              kvs.push(p);
            }
            prep_cp(v);
            if(_.has(v, "children") && _.get(sample_obj, "params." + v["param_name"], false) == true) { v["has_children"] = true; _.each(v["children"], function(c){ c["ischild"] = true; c["data-parent-param-name"] =  v["param_name"]; prep_cp(c); }) }
        })
        pdd = _.keyBy(kvs, "param_name");
        _.each(_.get(thesample, 'params', {}), function(v,k,o){  if(_.has(pdd, k)) { pdd[k]["current_val"] = v } else { kvs.push({ required: false, param_name: k, label: k, current_val: v })}})
        thesample.paramkvs = kvs;
        console.log(thesample);
        Mustache.parse(tmpl);
        document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(tmpl, thesample);
        const modalElem = document.querySelector("#glbl_modals_go_here .modal");
        modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
        const myModal = new bootstrap.Modal(modalElem);
        myModal.show();
    })
}