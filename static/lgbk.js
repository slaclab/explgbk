let lgbkabspath = function(path) { 
  return window.location.toString().split(pagepath)[0] + path; 
}

let lgbksetuptabs = function(tabload) {
  document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(tab => {
    tab.addEventListener('shown.bs.tab', event => {
        let target = event.target.getAttribute("data-bs-target"), taburl = event.target.getAttribute("data-lg-url");
        if("#"+tabname !== target) {
            const newtab = target.replace("#", "");
            console.log(`Changing the location to ${newtab}`);
            history.pushState({}, newtab, newtab);
            tabname=newtab;
            pagepath = pagepath.replace(new RegExp("\\/\\w+$"), "/"+tabname);
        }
        console.log(`Displaying tab ${target} using URL ${taburl}`);
        tabload(taburl, event.target);
        if(event.target.classList.contains("dropdown-item")) {
            new bootstrap.Dropdown(event.target.closest(".dropdown")).hide();
        }
    })
    tab.addEventListener('hidden.bs.tab', event => {
        let target = event.target.getAttribute("data-bs-target");
        console.log(`Hiding tab ${target}`);
        let trgt = document.querySelector(target); 
        trgt.querySelector(".tabcontainer").dispatchEvent(new Event("lg.hidden.bs.tab"));
        trgt.innerHTML="";
        document.querySelector("#toolbar_for_tab").innerHTML = "";
    })
  });
  new bootstrap.Tab(document.querySelector(`#myNavbar [data-bs-target="#${tabname}"]`)).show();
}

/*
 * Sets the current sample in the logbook titlebar.
 */
var setCurrentUISample = function() {
     var template = `<span><i class="fas fa-snowflake fa-lg" aria-hidden="true"></i></span>
     <span id="current_sample_name" class="ttip">{{ sample_showing_in_UI }}</span>`;
     Mustache.parse(template);
     var ttip_template = `<span class="ttiptext">
       <p>While the UI is showing data for <strong>{{ sample_showing_in_UI }}</strong>, the DAQ is currently processing <strong>{{ current_sample_at_DAQ }}</strong>.</p>
       <p>To change the sample being displayed in the UI, please click on the sample name and choose the current sample.</p>
     </span>`;
     Mustache.parse(ttip_template);
     var choose_sample_template = `{{#sample_names}}<tr data-sample="{{.}}"><td><span class="chsmpic"><i class="far fa-hand-point-right fa-lg"></i><span></td><td>{{.}}</td></tr>{{/sample_names}}`;
     Mustache.parse(choose_sample_template);
     $("#current_sample_lbl").removeClass("samples_different");
     $("#current_sample_lbl").prop("title", "");
     if(sample_showing_in_UI) {
         var samplesDict = {sample_showing_in_UI:sample_showing_in_UI, current_sample_at_DAQ:current_sample_at_DAQ};
         var rendered = $(Mustache.render(template, samplesDict));
         $("#current_sample_lbl").html(rendered);
         if(sample_showing_in_UI != current_sample_at_DAQ) {
             $("#current_sample_lbl").addClass("samples_different");
             $("#current_sample_name").tooltip({html: true, delay: 500, title: Mustache.render(ttip_template, samplesDict)});
         }
         if(!$("#current_sample_name").parent().hasClass("click_attached")){
           $("#current_sample_name").parent().on("click", function(){
             $(this).addClass("click_attached");
               $.when($.ajax("../../static/html/ms/chooseSample.html"), $.getJSON("ws/samples"))
               .done(function(d1, d2){
                   var tmpl = d1[0], samples = d2[0], sample_names = _.union(_.map(samples.value, "name"), ["Current Sample", "All Samples"]);
                   Mustache.parse(tmpl);
                   var rendered = $(Mustache.render(tmpl, samplesDict));
                   rendered.find("#choose_sample tbody").append($(Mustache.render(choose_sample_template, {sample_names: sample_names})));
                   rendered.find("#choose_sample tbody tr").on("click", function(){
                       var selected_sample = $(this).attr("data-sample");
                       if(selected_sample == "All Samples") {
                           sample_showing_in_UI = "All Samples";
                       } else if (selected_sample == "Current Sample") {
                           sample_showing_in_UI = current_sample_at_DAQ;
                       } else{
                           sample_showing_in_UI = selected_sample;
                       }
                       $("#glbl_modals_go_here").find(".edit_modal").modal("hide");
                       setCurrentUISample();
                       $(".tabcontainer").trigger("lg.refreshOnSampleChange");
                   });
                   $("#glbl_modals_go_here").append(rendered);
                   $("#glbl_modals_go_here").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#glbl_modals_go_here").empty(); });
                   $("#glbl_modals_go_here").find(".edit_modal").modal("show");
             });
         });
     }
     } else {
         $("#current_sample_lbl").empty();
     }
}

const elog_timezone = "America/Los_Angeles";
window.elog_formatdate = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(elog_timezone).format("MMM/D/YYYY")}};
window.elog_formatdatetime = function() { return function(dateLiteral, render) { var dateStr = render(dateLiteral); return dateStr == "" ? "" : moment(dateStr).tz(elog_timezone).format("MMM/D/YYYY HH:mm:ss")}};

let message_tmpl = `  <div class="toast-container top-0 end-0 p-3">
<div class="toast align-items-center {{colorclass}} data-bs-autohide="{{timeout}}" border-0" role="warning" aria-live="assertive" aria-atomic="true">
<div class="d-flex">
  <div class="toast-body">
    {{message}}
  </div>
  <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
</div>
</div></div>`; Mustache.parse(message_tmpl);

const showToast = function(msg, timeout, toastcolor) {
  const tstelem = document.querySelector("#glbl_toasts_go_here");
  tstelem.innerHTML = Mustache.render(message_tmpl, {message: msg, timeout: timeout, colorclass: toastcolor});
  const toast = new bootstrap.Toast(tstelem.querySelector(".toast"));
  toast.show();
}

var success_message = function(msg, timeout=5000) {
  showToast(msg, timeout, "text-bg-success");
}

var error_message = function(msg, timeout=5000) {
  showToast(msg, timeout, "text-bg-danger");
}

var info_message = function(msg, timeout=5000) {
  showToast(msg, timeout, "text-bg-info");
}

let delayFunction = function(fn, ms=500) {
    // Function to execute some other function after a delay; resetting each time this is called.
    // https://stackoverflow.com/questions/1909441/how-to-delay-the-keyup-handler-until-the-user-stops-typing
    let timer = 0
    return function(...args) {
        clearTimeout(timer)
        timer = setTimeout(fn.bind(this, ...args), ms || 0)
    }
}
