export function tabshow(target) {
    const tabpanetmpl = `<div class="sitespecific_iframe_parent">
    <iframe class="sitespecific_iframe" src="https://lcls.slac.stanford.edu/overview">
    </iframe>
    </div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;
}
