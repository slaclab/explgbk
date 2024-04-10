export function patch_modal_defs(paramdefs) {
    paramdefs.forEach((paramdef) => {
        paramdef["param_type"] = _.get(paramdef, "param_type", "string");
        paramdef["label"] = _.get(paramdef, "label", paramdef["param_name"]);
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
