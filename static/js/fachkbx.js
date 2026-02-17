const templateElem = document.createElement("template");

templateElem.innerHTML = `<span></span>`;

export class LgbkFACheckbox extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.appendChild(templateElem.content.cloneNode(true));
    this.span = this.shadowRoot.querySelector("span");
    this.checked = false;
    this.disabled = false;
  }

  faIcon(prefix, iconName) {
    return window.FontAwesome.icon(window.FontAwesome.findIconDefinition({prefix: prefix, iconName: iconName})).html
  }

  render() { 
    this.span.innerHTML = this.checked ? this.faIcon('fas','check') : this.faIcon('far', 'square');
  }

  connectedCallback() {
    const style = document.createElement("style");
    style.textContent = `svg {
        display: inline-block;
        margin-top: 0.25rem;
        height: 1.0rem;
    }`;
    this.shadowRoot.appendChild(style);

    this.render();
    this.span.addEventListener("click", this.handleClick);
  }

  disconnectedCallback() {
    this.span.removeEventListener("click", this.handleClick);
  }

  static get observedAttributes() {
    return ["disabled", "checked"];
  }

  boolfromattr(attrname) {
    const attrval = this.getAttribute(attrname);
    return !(_.isNil(attrval) || attrval === "false");
  }

  attributeChangedCallback(name, oldVal, newVal) {
    console.log(`Attribute ${name} changed from ${oldVal} to ${newVal}`);
    if (name === "checked") {
      this.checked = this.boolfromattr("checked");
      this.render();
      this.dispatchEvent(new Event("change", {bubbles: true}));
    } else if (name === "disabled") {
      this.disabled = this.boolfromattr("disabled");
    }
  }

  handleClick = () => {
    if(this.disabled) return;
    this.setAttribute("checked", this.checked ? "false": "true")
  }
}

customElements.define('lgbk-checkbox', LgbkFACheckbox);