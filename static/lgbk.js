/*
 *  Fetches data from the server using JSON calls specified in the requestobjs.
 *  Fetches the mustache template specified in the  tmpl object.
 *  Stores the data obtained from the JSON calls in the context object
 *  Renders the template using context object.
 *  Sets the html() for the specified container object.
 */
var getJSONAndRender = function(tmpl, requestobjs, context, destcontainer) {
	function deferred(call, varname, context, jsonp) {
		jsonp = (typeof jsonp !== 'undefined') ?  jsonp : true;
		var ajaxfn = jsonp ? $.getJSON : $.ajax;
		return ajaxfn(call)
		.done(function(data) { context[varname] = data; })
		.fail(function(jqXHR, textStatus) { console.log("Request failed: " + textStatus); });
	}

	var ajax_calls = [];
	ajax_calls.push(deferred(tmpl, "template", context, false));
	for (var i = 0; i < requestobjs.length; i++) {
		ajax_calls.push(deferred(requestobjs[i], requestobjs[i]["ctxnm"], context))
	}
	$.when.apply(this, ajax_calls).done(function() {
		if (typeof context.postGet === 'function') {
			context.postGet();
		}
		var template = context['template'];
		Mustache.parse(template);
		var rendered = Mustache.render(template, context);
		destcontainer.html(rendered);

		if (typeof context.postRender === 'function') {
			context.postRender();
		}
	});
}

/*
 * Sets the current sample in the logbook titlebar.
 */
var setCurrentUISample = function() {
     var template = `<i class="fa fa-snowflake-o fa-lg" aria-hidden="true"></i>
     <span id="current_sample_name" class="ttip">{{ sample_showing_in_UI }}</span>`;
     Mustache.parse(template);
     var ttip_template = `<span class="ttiptext">
       <p>While the UI is showing data for <strong>{{ sample_showing_in_UI }}</strong>, the DAQ is currently processing <strong>{{ current_sample_at_DAQ }}</strong>.</p>
       <p>To change the sample being displayed in the UI, please click on the sample name and choose the current sample.</p>
     </span>`;
     Mustache.parse(ttip_template);
     var choose_sample_template = `{{#sample_names}}<tr data-sample="{{.}}"><td><i class="fa fa-hand-o-right fa-lg"></i></td><td>{{.}}</td></tr>{{/sample_names}}`;
     Mustache.parse(choose_sample_template);
     $("#current_sample_lbl").removeClass("samples_different");
     $("#current_sample_lbl").prop("title", "");
     if(sample_showing_in_UI) {
         var samplesDict = {sample_showing_in_UI:sample_showing_in_UI, current_sample_at_DAQ:current_sample_at_DAQ};
         var rendered = $(Mustache.render(template, samplesDict));
         $("#current_sample_lbl").html(rendered);
         if(sample_showing_in_UI != current_sample_at_DAQ) {
             $("#current_sample_lbl").addClass("samples_different");
             $("#current_sample_name").append(Mustache.render(ttip_template, samplesDict));
         }
         $("#current_sample_name").on("click", function(){
             $.when($.ajax("../../static/html/ms/chooseSample.html"), $.getJSON("ws/samples"))
             .done(function(d1, d2){
                 var tmpl = d1[0], samples = d2[0], sample_names = _.union(_.map(samples.value, "name"), ["Current Sample", "All Samples"]);
                 Mustache.parse(tmpl);
                 var rendered = $(Mustache.render(tmpl, samplesDict));
                 rendered.find("#choose_sample tbody").append($(Mustache.render(choose_sample_template, {sample_names: sample_names})));
                 rendered.find("#choose_sample tr").on("click", function(){
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
                     $(".tabcontainer").trigger("lg.refresh");
                 });
                 $("#glbl_modals_go_here").append(rendered);
                 $("#glbl_modals_go_here").find(".edit_modal").on("hidden.bs.modal", function(){ $(".modal-body").html(""); $("#glbl_modals_go_here").empty(); });
                 $("#glbl_modals_go_here").find(".edit_modal").modal("show");
           });
       });
     } else {
         $("#current_sample_lbl").empty();
     }
}

/*
 * Get the value of the first URL parameter with the given name.
 * Note that there can be more than one parameter with the same name; if need be, extend this to return an array later.
 */
var getURLParameter = function(paramName) {
	var queryString = window.location.search;
	if(!_.isNil(queryString) && queryString.length > 2) {
		var queries = queryString.substring(1).split("&");
		for ( i = 0, l = queries.length; i < l; i++ ) {
			var parts = queries[i].split('='), name = parts[0], val =  decodeURIComponent(parts[1]);
            if(name == paramName) {
                return val;
            }
		}
	}
    return null;
}


var content_editable_trigger_change = function(rowRendered) {
  rowRendered.find("[contenteditable]").on('focus', function() {
      var $this = $(this);
      $this.data('before', $this.html());
      return $this;
  }).on('focusout', function() {
      var $this = $(this);
      if ($this.data('before') !== $this.html()) {
          $this.data('before', $this.html());
          $this.trigger('change');
      }
      return $this;
  });
}
