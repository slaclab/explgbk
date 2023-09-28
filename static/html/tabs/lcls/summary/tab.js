export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer sitespecific_iframe_parent" id="summaries_tab"></div>`;
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;

  var smtmpl = `<iframe class="sitespecific_iframe" src="../../../experiment_results/{{instrument_name}}/{{experiment_name}}/"></iframe>`;
  Mustache.parse(smtmpl);
  var rendered = Mustache.render(smtmpl, {experiment_name: experiment_name, instrument_name: instrument_name})
  $("#summaries_tab").empty().append(rendered);
}
