$(function() {
    $(document).ready(function() {
    	$('#start_time').datetimepicker({defaultDate: moment(), sideBySide: true });
    	$('#end_time').datetimepicker({defaultDate: moment().add(2, 'days'), sideBySide: true });
    	$.getJSON(instruments_url).done(function(data) {
    		_.each(data.value, function(instr) {
    			$("#instrument").append('<option value="' + instr["_id"] + '">' + instr["_id"] + '</option>');
    		});
    	});
    	validations = [
    		[function() { return $.trim($("#experiment_name").val()) == ""; }, "Experiment name cannot be blank."],
    		[function() { return $.trim($("#instrument").val()) == ""; }, "Please choose a valid instrument."],
    		[function() { return $.trim($("#posix_group").val()) == ""; }, "Please choose a posix group for authorization."],
    		[function() { return $.trim($("#start_time input").val()) == ""; }, "Please choose a valid start time."],
    		[function() { return $.trim($("#end_time input").val()) == ""; }, "Please choose a valid end time."],
    		[function() { return $('#end_time').data("DateTimePicker").date().isSameOrBefore($('#start_time').data("DateTimePicker").date(), 'minute') ; }, "The end time should be after the start time."],
    		[function() { return $.trim($("#leader_account").val()) == ""; }, "Please specify the UNIX account of the leader for the experiment."],
    		[function() { return $.trim($("#pi_name").val()) == ""; }, "Please specify the full name of the principal investigator."],
    		[function() { return $.trim($("#pi_email").val()) == ""; }, "Please specify the email address for the principal investigator."],
    		[function() { var email = $.trim($("#pi_email").val()); var re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/; return !re.test(email.toLowerCase()); }, "Please specify the email address for the principal investigator."],
    		[function() { return $.trim($("#description").val()) == ""; }, "A brief description of the experiment is very helpful."]
    	];
    	
    	$("#panel_btn").on("click", function(e) {
			e.preventDefault();
    		
    		// Various validations
    		var v_failed = false;
    		_.each(validations, function(validation, i) {
    			// console.log("Trying validation " + i + "" + validation[1]);
    			if(validation[0]()) {
        			$("#validation_message").html(validation[1]);
        			$("#validation_modal").modal();
        			e.preventDefault();
        			v_failed = true;
        			return false;
    			}
    		});
    		if (v_failed) { e.preventDefault(); return; }
    		var experiment_name = $.trim($("#experiment_name").val());
    		var registration_doc = {
    				"name" : experiment_name,
    				"instrument" : $.trim($("#instrument").val()),
    				"description" : $.trim($("#description").val()),
    				"start_time" : $('#start_time').data("DateTimePicker").date().toJSON(),
    				"end_time" : $('#end_time').data("DateTimePicker").date().toJSON(),
    				"leader_account" : $.trim($("#leader_account").val()),
    				"contact_info" : $.trim($("#pi_name").val()) + "(" + $.trim($("#pi_email").val()) + ")",
    				"posix_group" : $.trim($("#posix_group").val())
    		};
    		$.ajax({
    			type: "POST",
    			contentType: "application/json; charset=utf-8",
    			url: register_experiment_url + "?experiment_name=" + encodeURIComponent(experiment_name),
    			data: JSON.stringify(registration_doc),
    			dataType: "json"
    		})
    		.done(function(data, textStatus, jqXHR) {
    			if(data.success) {
        			console.log("Successfully submitted experiment " + experiment_name);
        			window.location=experiment_name.replace(" ", "_") + "/";
    			} else {
    				alert("Server side exception registering new experiment " + data.errormsg);
    			}
    		})
    		.fail( function(jqXHR, textStatus, errorThrown) { console.log(errorThrown); alert("Server side exception registering new experiment " + jqXHR.responseText); })
    	});
    });
});
