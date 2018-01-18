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
