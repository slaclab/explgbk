export function miscSetup() {
    _.each(privileges, function(v,k){if(v){$("#lgbk_body").find(".priv_"+k).removeClass("d-none");}})
}