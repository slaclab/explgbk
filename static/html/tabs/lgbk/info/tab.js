export function tabshow(target) {
    const baseUrl = target.getAttribute("data-lg-url").split("/static")[0];
    const infoUrl = baseUrl + "/lgbk/"+experiment_name+"/ws/info";
    const templateUrl = baseUrl + "/static/html/ms/info_" + logbook_site + ".html";
    console.log("Inside tab show for sessions " + infoUrl);
    Promise.all([fetch(new Request(infoUrl)), fetch(new Request(templateUrl))])
    .then((resps) => {
        return Promise.all([resps[0].json(), resps[1].text()]);
    })
    .then((vals) => {
        const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="info_tab"><div class="row content"><div class="lgcontent col-12"></div></div></div>`;
        let [ inforesp, tmpl ]= vals;
        let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
        trgt.innerHTML=tabpanetmpl;

        const info = inforesp.value, contact_info = info.contact_info, parts = contact_info.split(')')[0].split('(');
        info.contact_name = parts[0];
        info.contact_email = parts[1];
        Mustache.parse(tmpl);
        $("#info_tab").find(".lgcontent").empty().append($(Mustache.render(tmpl, {info: info, FormatDate: elog_formatdatetime})));
        $("#info_tab").trigger("info_loaded", info);
    })
}