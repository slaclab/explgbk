let tmpl = `<div class="container-fluid text-center">
<div class="table-responsive">
    <table class="table table-condensed table-striped table-bordered" id="prjlisttbl">
      <thead><tr><th>Name</th><th>Description</th><th>PI</th></tr></thead>
      <tbody>{{#projects}}<tr><td><a href="{{_id}}/sampprep">{{name}}</a></span></td><td>{{description}}</td><td>{{contact_info.name}}</td></tr>{{/projects}}</tbody>
    </table>
  </div>
</div>`;
Mustache.parse(tmpl);

async function addeditproject() {
  const { modalshow } = await import(lgbkabspath("/static/html/tabs/project/prjlist/prjmdl.js"));
  modalshow();
}  

export function tabshow(target) {
  fetch(new Request("../ws/projects"))
  .then((response) => {
    if (!response.ok) { throw new Error(`HTTP error! Status: ${response.status}`); }
    return response.json();
  }).then((resp) => {
    console.log(resp);
    let projects = resp["value"];
    target.innerHTML=Mustache.render(tmpl, { projects: projects});
  })

  document.querySelector("#toolbar_for_tab").innerHTML = `<span class="addprj"><i class="fa-solid fa-plus fa-lg" title="Create a new project"></i></span>`;
  document.querySelector("#toolbar_for_tab .addprj").addEventListener("click", () => { addeditproject(); });
}
