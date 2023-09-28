const templateElem = document.createElement("template");

templateElem.innerHTML = `<div class="col-5"><input type="text" class="form-control cp_key"/></div>
  <div class="col-5"><input type="text" class="form-control cp_value"/></div>
  <div class="col-2 px-2 py-2">
    <span class="param_action delparam icon"><i class="fa-solid fa-trash fa-lg"></i></span>
    <span class="param_action addparam icon"><i class="fa-solid fa-plus fa-lg"></i></span>
  </div>`;

export class LgbkCustomParam extends HTMLElement {
  constructor() {
    super();
    this.name = "";
    this.value = "";
    this.addTemplate = '<lgbk-custom-param/>'
  }

  render() { 
    this.querySelector(".cp_key").setAttribute("value", this.name);
    this.querySelector(".cp_value").setAttribute("value", this.value);
  }

  connectedCallback() {
    this.appendChild(templateElem.content.cloneNode(true));
    this.render();
    this.querySelector(".addparam").addEventListener("click", this.addParam);
    this.querySelector(".delparam").addEventListener("click", this.deleteParam);
    this.querySelector(".cp_key").addEventListener("change", this.keyChange);
    this.querySelector(".cp_value").addEventListener("change", this.valueChange);
  }

  disconnectedCallback() {
  }

  static get observedAttributes() {
    return ["disabled", "name", "value"];
  }

  attributeChangedCallback(name, oldVal, newVal) {
    console.log(`Attribute ${name} changed from ${oldVal} to ${newVal}`);
    if (name === "name") {
      this.name = newVal;
      this.dispatchEvent(new Event("change", {bubbles: true}));
    } else if (name === "value") {
        this.value = newVal;
        this.dispatchEvent(new Event("change", {bubbles: true}));
    } else if (name === "disabled") {
      this.disabled = this.boolfromattr("disabled");
    }
  }

  setAddTemplate = (newaddtmpl) => { 
    this.addTemplate = newaddtmpl;
  }

  addParam = () => {
    let tempelem = document.createElement("div");
    tempelem.innerHTML = this.addTemplate;
    let lcp = tempelem.firstChild;
    this.after(lcp);
    lcp.setAddTemplate(this.addTemplate);
  }

  deleteParam = () => {
    this.parentNode.removeChild(this);
  }

  keyChange = (event) => { 
    this.setAttribute("name", event.target.value);
  }

  valueChange = (event) => { 
    this.setAttribute("value", event.target.value);
  }

  checkForInvalidChars = (val) => {
    return !/^[\w/_-]+$/.test(_.trim(val));
  }

  validate = (errormsg) => { 
    let newname = _.trim(this.querySelector(".cp_key").value);
    let newvalue = _.trim(this.querySelector(".cp_value").value);
    console.log(`In custom param validation, new name is "${newname}" and "${newvalue}"`);
    let nameEmpty = _.isNil(newname) || newname === "";
    let valEmpty = _.isNil(newvalue) || newvalue === "";
    if(nameEmpty && valEmpty) return true;
    if(!nameEmpty && valEmpty) {
      errormsg(`We do not support custom names (${newname}) without a value`);
      return false;
    }
    if(nameEmpty && !valEmpty) {
      errormsg(`Custom parameters with a value (${newvalue}) must have a name`);
      return false;
    }

    if(this.checkForInvalidChars(newname)) {
      errormsg("Please restrict custom parameter names to alphanumeric characters, dashes, slashes and underscores.")
      return false;
  }


    return true;
  }

  mergeinto = (obj) => { 
    let newname = _.trim(this.querySelector(".cp_key").value);
    let newvalue = _.trim(this.querySelector(".cp_value").value);
    let nameEmpty = _.isNil(newname) || newname === "";
    let valEmpty = _.isNil(newvalue) || newvalue === "";
    if(!nameEmpty && !valEmpty) {
      obj[newname] = newvalue;
    }
  }
}

customElements.define('lgbk-custom-param', LgbkCustomParam);