const SAMPLE_MODAL = lgbkabspath("/static/html/mdls/samples/modal.js");
const INFO_MODAL = lgbkabspath("/static/html/mdls/samples/info.js");
const ALL_SAMPLES_URL = lgbkabspath(`/lgbk/ws/projects/${prjid}/samples/`);

async function loadAndShowSampleModal(target, sampleid) {
    const { modalshow } = await import(SAMPLE_MODAL);
    modalshow(sampleid, ALL_SAMPLES_URL, () => { tabshow(target) });
}

async function loadAndShowInfoModal(sampleid) { 
    const { modalshow } = await import(INFO_MODAL);
    modalshow(sampleid, ALL_SAMPLES_URL, () => { });
}  

export function tabshow(target) {
    const baseUrl = target.getAttribute("data-lg-url").split("/static")[0];
    const templateurl = baseUrl + "/static/html/tabs/project/samples/samples.html";
    Promise.all([fetch(new Request(ALL_SAMPLES_URL)), fetch(new Request(templateurl))])
    .then((resps) => {
        return Promise.all([resps[0].json(), resps[1].text()]);
    })
    .then((vals) => {
        let [ sampresp, tmpl ]= vals, samples = sampresp["value"];
        let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
        trgt.innerHTML=tmpl;
        const tbody = trgt.querySelector("tbody");
        const template = trgt.querySelector("#projectsample");
        _.each(samples, (sample) => { 
            const clone = template.content.cloneNode(true);
            let td = clone.querySelectorAll("td");
            td[0].textContent = _.get(sample, "name", "N/A");
            td[1].textContent = _.get(sample, "description", "N/A");
            td[2].innerHTML = `<span class="info icon px-1"><i class="fa-solid fa-info-circle fa-lg"></i></span><span class="edit icon px-1"><i class="fa-solid fa-edit fa-lg"></i></span>`;
            td[2].querySelector("span.info").addEventListener("click", () => loadAndShowInfoModal(sample["_id"]))
            td[2].querySelector("span.edit").addEventListener("click", () => loadAndShowSampleModal(target, sample["_id"]))
            tbody.appendChild(clone);
        })


        document.querySelector("#toolbar_for_tab").innerHTML = `<span class="tlbricn newsample"><i class="fa-solid fa-square-plus fa-lg" title="Create a new sample"></i></span>`;
        document.querySelector("#toolbar_for_tab .newsample").addEventListener("click", (event) => {
            loadAndShowSampleModal(target, null);
        })    
    })
} 