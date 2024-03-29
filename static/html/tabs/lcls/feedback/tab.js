let survey_templates = {
    "section_header": `<div><div class="fd_section_hdr col-sm-9"><span>{{header}}<span></div></div>`,
    "plain-header": `<div class="fd_plain_hdr col-sm-9"><span class="col-sm-8">{{header}}<span></div>`,
    "readonly_text": `<div class="fd_item fd_readonly col-sm-9"><span class="col-sm-8">{{header}}</span><span data-attr-id="{{id}}" data-attr-text="true"></span></div>`,
    "input": `<div class="fd_item fd_input col-sm-9"><span class="col-sm-8">{{{header}}}</span><input class="ms-2" maxlength="3" size="3" data-attr-id="{{id}}"></div>`,
    "checkbox": `<div class="fd_item fd_input col-sm-9"><span class="col-sm-8">{{{header}}}</span><input class="ms-2" type="checkbox" data-attr-id="{{id}}"></div>`,
    "selector": `<div class="fd_item fd_input col-sm-9"><span class="col-sm-8">{{{header}}}</span><select class="ms-2" data-attr-id="{{id}}"><option val="1">1</option><option val="2" selected>2</option><option val="3">3</option><option val="4">4</option><option val="5">5</option></select></div>`,
    "textarea": `<div class="fd_item col-sm-9"><span class="col-sm-8">{{{header}}}</span></div><div class="fd_item fd_notes col-sm-9"><textarea class="col-sm-8" rows="8" cols="80" data-attr-id="{{id}}"></textarea></div>`
},
notes_template = `<div class="fd_survey_notes d-none"><textarea rows="4" cols="60" data-attr-id="{{id}}-notes"></textarea></div>`,
last_changed_template = `<div>{{#last_modified_by}}Last modified by {{last_modified_by}}</div><div> at {{#FormatDate}}{{last_modified_at}}{{/FormatDate}}{{/last_modified_by}}</div>`;

_.each(survey_templates, function(v, k){ Mustache.parse(v); });
Mustache.parse(notes_template);
Mustache.parse(last_changed_template);

let renderSurveyItem = function(survey_elem, currentDOMelem) {
    var rendered = $(Mustache.render(survey_templates[survey_elem['type']], survey_elem));
    if(_.has(survey_elem, 'groups')) {
        var chid_container = $('<div class="fd_subitem"></div>');
        if(_.get(survey_elem, 'toggler', false)) {
            chid_container.addClass("d-none");
            rendered.find("input[type=checkbox]").on("change", function(){ if($(this).is(':checked')){ $(this).closest(".fd_item").find(".fd_subitem").removeClass('d-none'); } else { $(this).closest(".fd_item").find(".fd_subitem").addClass('d-none') }});
        }
        _.each(_.get(survey_elem, 'groups'), function(si){
            renderSurveyItem(si, chid_container);
        })
        rendered.append(chid_container);
    }
    if(_.get(survey_elem, 'notes', false)) {
        rendered.append(Mustache.render(notes_template, survey_elem));
        if(survey_elem['type'] == "selector") {
            rendered.find("select").on("change", function(){ if(parseInt($(this).val()) >= 4){ $(this).closest(".fd_item").find(".fd_survey_notes").removeClass('d-none'); } else { $(this).closest(".fd_item").find(".fd_survey_notes").addClass('d-none') }});
        } else {
            rendered.find("input").on("change", function(){ if($(this).is(':checked')){ $(this).closest(".fd_item").find(".fd_survey_notes").removeClass('d-none'); } else { $(this).closest(".fd_item").find(".fd_survey_notes").addClass('d-none') }});
        }
    }

    currentDOMelem.append(rendered);
}

let update_survey_val = function(attr_name, attr_val) {
    console.log("Updating " + attr_name + " to value " + attr_val);
    $.getJSON({url: "ws/add_feedback_item", data: {item_name: attr_name, item_value: attr_val}, method: "POST"})
    .done(function(){
      success_message("Updated");
        $.getJSON("ws/get_feedback_document").done(function(data){
            var feedback_doc = data.value;
            feedback_doc.FormatDate = elog_formatdatetime;
            $("#feedback_tab").find(".fd_last_modified").empty().append(Mustache.render(last_changed_template, feedback_doc));
        })
    })
    .fail(function(jqXHR, textStatus, errorThrown) { error_message("Server side error " + jqXHR.responseText); })
}

export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="feedback_tab">
    <div class="container-fluid text-center">
        <div class="row">
            <div class="col-9 feedback_content"></div>
            <div class="fd_callout col-sm-3">
                <div class="fd_instructions">
                    <div class="ins_ls_title">Use these definitions for the numbers.</div>
                    <ul>
                        <li>1. Easier than expected</li>
                        <li>2. As expected</li>
                        <li>3. Harder than expected</li>
                        <li>4. Difficult</li>
                        <li>5. Fatal flaw, do not do again</li>
                    </ul>
                    <div class="fd_text_instructions">All your modifications will be automatically recorded in a database as you make them.
                        To save a note, please click outside (or tab out of) the text area.
                    </div>
                </div>
               <div class="fd_last_modified"></div>
            </div>
        </div>
    </div>
    </div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

    const feedback_survey_def = `../../static/json/${logbook_site}/feedback.json`;
    $.when($.getJSON(feedback_survey_def), $.getJSON("ws/get_feedback_document")).done(function(d0, d1){
        var topSurveyElem = $("#feedback_tab").find(".feedback_content").first(), feedback_defs = d0[0], feedback_doc = d1[0].value;
        feedback_doc.FormatDate = elog_formatdatetime;
        topSurveyElem.empty();
        $("#feedback_tab").find(".fd_last_modified").empty().append(Mustache.render(last_changed_template, feedback_doc));
        _.each(feedback_defs, function(si){ renderSurveyItem(si, topSurveyElem)});
        _.forOwn(feedback_doc, function(value, name){
            $("#feedback_tab").find("[data-attr-id=" + name + "]").val(value).trigger("change");
            if(value == "1") {
                $("#feedback_tab").find("[type=checkbox][data-attr-id=" + name + "]").prop('checked', true).trigger("change");
            }
            $("#feedback_tab").find("[data-attr-id=" + name + "][data-attr-text]").text(feedback_doc[name]);
        })
        $("#feedback_tab").find("[type=checkbox]").on("change", function(){ update_survey_val($(this).attr("data-attr-id"), $(this).is(':checked') ? "1" : "0")});
        $("#feedback_tab").find("[data-attr-id][type!=checkbox]").on("change", function(){ update_survey_val($(this).attr("data-attr-id"), $(this).val())});
    });
}