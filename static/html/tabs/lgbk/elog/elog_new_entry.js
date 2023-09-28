var summernote_options = {toolbar: [
    // [groupName, [list of button]]
    ['para', ['ul', 'ol', 'table', 'link', 'hr', 'paragraph', 'style']],
    ['font', ['fontname', 'fontsize', 'color']],
    ['style', ['bold', 'italic', 'clear']],
    ['help', ['codeview', 'help']]
]};

var check_session_timeout = function() {
    if(auth_expiration_time > 1000000000 && moment.unix(auth_expiration_time).isSameOrBefore(moment().add(5, 'minutes'))) {alert("Your session is about to expire. Please log back in to renew your session."); return true; }
}

var email_selector = function(content_div) {
    var elog_emails = `../${experiment_name}/ws/elog_emails`;
    $.getJSON(elog_emails).done(function(dat){
        var existing_emails = dat.value;
        var email_choices = _.map(existing_emails, function(em){ return {email: em}});
        var selected_items = _.split(content_div.find(".email_input").val(), " ");
        content_div.find(".email_select").selectize({persist: false, valueField: 'email', labelField: 'email', maxItems: null, options: email_choices, items: selected_items,
          render: { item: function(item, escape)   { return "<div class='selectedoption'><span>" + escape(item['email']) + "</span></div>"; },
                    option: function(item, escape) { return "<div class='seloption'><span>" + escape(item["email"]) + "</span></div>"; }
                },
                create: function(input) { return {email: input }}});
        content_div.find(".email_select").on("change", function() {
            content_div.find(".email_input").val(_.join(content_div.find(".email_select").val(), " "));
        })
    });
}

var tag_selector = function(content_div) {
    var elog_tags = `../${experiment_name}/ws/get_elog_tags`;
    $.getJSON(elog_tags).done(function(dat){
        var tags_choices = _.map(dat.value, function(t){ return {tag: t} });
        var selected_items = _.split(content_div.find(".tag_input").val(), " ");
        content_div.find(".tag_select").selectize({persist: false, valueField: 'tag', labelField: 'tag', createOnBlur: true, maxItems: null, options: tags_choices, items: selected_items,
          render: { item: function(item, escape)   { return "<div class='selectedoption'><span>" + escape(item['tag']) + "</span></div>"; },
                    option: function(item, escape) { return "<div class='seloption'><span>" + escape(item['tag']) + "</span></div>"; }
                },
                create: function(input) { return {tag: input }}});
        content_div.find(".tag_select").on("change", function() {
            content_div.find(".tag_input").val(_.join(content_div.find(".tag_select").val(), " "));
        })
    });
}

var current_text_mode_html=false;

var html_selector = function(content_div) {
    content_div.find(".elog_html").on("click", function(){ 
        content_div.find(".log_title_div").removeClass("d-none");
        $(this).remove(); 
        $('#elog_new_entry_log_text').summernote(summernote_options);
        content_div.find(".log_text_div").find('[data-toggle="dropdown"]').attr("data-bs-toggle", "dropdown");
        current_text_mode_html=true;
    });
}

export function new_entry_click(e, entry, parent_id) {
    if(check_session_timeout()) return;
    e.preventDefault();
    $.when($.ajax('../../static/html/tabs/lgbk/elog/elog_new_entry.html'), $.getJSON("ws/current_run"), $.getJSON("ws/get_instrument_elogs"))
    .done(function(modal_txt, cur_run, inselgsresp){
        var current_run_num =_.get(cur_run[0], "value.num", ""), ins_elogs = inselgsresp[0].value, mdl = $(Mustache.render(modal_txt[0], { entry: entry, parent_id: parent_id, current_run_num: current_run_num, post_to_instrument_elogs: (ins_elogs.length > 0), instrument_elogs: ins_elogs }));
        mdl.find("#elog_new_entry_file_upload").on("change", function(){ let fsel = $(this)[0].files.length; $(this).closest(".custom-file").find(".custom-file-label").text(fsel + " file" + (fsel==1 ? "" : "s") + " selected")})
        $("#elog_content").prepend(mdl);
        email_selector($("#elog_content"));
        tag_selector($("#elog_content"));
        html_selector($("#elog_content"));
        $("#elog_new_entry_modal_post").on("click", function (e) {
           var formData = new FormData($('#elog_new_entry_form')[0]);
           if(current_text_mode_html) {
               if(_.isEmpty($.trim($("#elog_new_entry_log_title").val()))) { $("#elog_new_entry_modal").find(".validation_warning").html("Please enter a title for the log message"); return false; }
               if(_.isEmpty($.trim($("#elog_new_entry_log_text").val()))) { $("#elog_new_entry_modal").find(".validation_warning").html("Please enter some text for the log message"); return false; }
           } else {
               if(_.isEmpty($.trim($("#elog_new_entry_log_text").val()))) { $("#elog_new_entry_modal").find(".validation_warning").html("Please enter some text for the log message"); return false; }
           }
           if($('#elog_new_entry_form').find(".files_div").find("[name='files']")[0].files.length <= 0) { console.log("No files specified; removing control to cater to Safari."); $('#elog_new_entry_form').find(".files_div").remove(); }
           $.ajax({
                 url: _.isNil(entry) ? 'ws/new_elog_entry' : 'ws/modify_elog_entry?_id='+encodeURIComponent(entry["_id"]),
                 data: formData,
                 type: 'POST',
                 contentType: false, // Needed
                 processData: false // Needed
             })
             .done(function(data, textStatus, jqXHR) {
                 if(data.success) {
                     console.log("Successfully posted elog entry");
                 } else {
                     error_message("Server side exception posting new elog entry " + data.errormsg);
                 }
             })
             .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); error_message("Server side exception posting new elog entry " + jqXHR.responseText); })
           $("#elog_new_entry_modal").modal("hide");
        });
        $("#elog_new_entry_modal").modal("show");
    });
}

export function followup_function(e) {
    if(check_session_timeout()) return;
    var entry = $(this).closest(".edat").data("entry");
    return new_entry_click(e, null, entry["_id"]);
 }

 export function edit_elog_entry(e) {
    if(check_session_timeout()) return;
    var entry = $(this).closest(".edat").data("entry");
    return new_entry_click(e, entry, null);
 }

