

const errormsg = function(message) {
  console.log(message);
  let errelem = document.querySelector("#glbl_modals_go_here .modal .errormsg");
  errelem.classList.remove("d-none");
  errelem.innerHTML = message;
}

const editcreatefn = function(theins, onCompletion) {
  const modalUrl = lgbkabspath("/static/html/ops/ins/insedit.html");
  const defsUrl = lgbkabspath("/lgbk/get_modal_param_definitions?modal_type=instrument");

  Promise.all([fetch(modalUrl), fetch(defsUrl)])
  .then((resps) => { return Promise.all([resps[0].text(), resps[1].json()])})
  .then((vals) => {
    let [ tmpl, mdlparamsresp ] = vals, mdlparams = mdlparamsresp["value"]["params"];
    Mustache.parse(tmpl);
    document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(tmpl, theins);
    const modalElem = document.querySelector("#glbl_modals_go_here .modal");
    const formElem = modalElem.querySelector("form");        
    const isEditing = _.has(theins, "_id");
    if (isEditing) {
      console.log("We are editing the instrument; turning off non-editable values");
      modalElem.querySelectorAll("[data-lg-noedit]").forEach((elem) => { 
        elem.readOnly = true; 
        elem.disabled = true;
      })
      modalElem.querySelector(".aded_ins").innerText = "Update";
    }


    import(lgbkabspath("/static/html/mdls/common/mdlparams.js")).then((mod) => { 
      const { LgbkCustomModalParams } = mod;
      let mdlParamsJS = new LgbkCustomModalParams(mdlparams, errormsg);
      console.log(mdlParamsJS);
      mdlParamsJS.render(theins);

      const myModal = new bootstrap.Modal(modalElem);
      myModal.show();
      
      modalElem.querySelector(".aded_ins").addEventListener("click", (event) => {
          event.preventDefault();
          modalElem.querySelector(".errormsg").innerHTML = "";
          let newins = {};
          let name = modalElem.querySelector('[data-lg-attr="name"]').value;
          if(_.isNil(name) || _.isEmpty(name)) {
              errormsg("The sample name cannot be a blank string");
              return;
          }

          let description = modalElem.querySelector('[data-lg-attr="description"]').value;
          if(_.isNil(description) || _.isEmpty(description)) {
              errormsg("Please enter a description");
              return;
          }

          newins["_id"] = name;
          newins["description"] = description;
          newins["color"] = modalElem.querySelector('[data-lg-attr="color"]').value;

          if(!mdlParamsJS.validate(newins)){
              return;
          }

          mdlParamsJS.createOrUpdate(lgbkabspath("/lgbk/ws/instruments/"), isEditing ? newins["_id"] : null, newins, () => { myModal.hide(); onCompletion(); });
      })
    })
  })
}


export function tabshow(target) {
  const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="ops_instruments_tab">
  <div class="row">
      <div class="table-responsive">
          <table class="table table-condensed table-striped table-bordered" id="instrumentstbl">
              <thead><tr><th>Name</th><th>Description</th><th>Number of Stations</th><th>Edit</th></tr></thead>
              <tbody></tbody>
          </table>
      </div>
  </div>
  </div>`;
  const instmpl = `{{#value}}<tr data-insname={{_id}}>
    <td class="instrument_lbl" style="background:{{color}}; color:{{#color}}white{{/color}}{{^color}}black{{/color}}; " >{{ _id }}</td>
    <td>{{ description }}</td>
    <td>{{ params.num_stations}}</td>
    <td> <span class="editinsbtn"><i class="fas fa-edit fa-lg"></i></span></td>
  </tr>{{/value}}`;
  Mustache.parse(instmpl);
  
  let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
  trgt.innerHTML=tabpanetmpl;


  fetch("../ws/instruments")
  .then((resp) => { return resp.json() })
  .then((instruments) => {
    document.querySelector("#instrumentstbl tbody").innerHTML = Mustache.render(instmpl, instruments);
    document.querySelectorAll("#instrumentstbl tbody .editinsbtn").forEach((bt) => { 
      bt.addEventListener("click", (e) => {
        e.preventDefault();
        const insname = e.target.closest("tr").getAttribute("data-insname");
        console.log("Editing instrument " + insname);
        const theins = _.find(instruments.value, function(instr){ return instr._id == insname; });
        editcreatefn(theins, () => { window.location.reload()});  
      })
    })
  });

  document.querySelector("#toolbar_for_tab").innerHTML = `<span id="new_instrument" title="Add a new instrument"><i class="fas fa-plus fa-lg"></i></span>`;
  document.querySelector("#toolbar_for_tab #new_instrument").addEventListener("click", () => editcreatefn({}, () => { window.location.reload()}));
}
