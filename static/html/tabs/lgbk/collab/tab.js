
var collab_tr_tmpl = `{{#collabs}}<tr data-uid="{{ uid }}"><td>{{#is_group}}<i class="fas fa-users" aria-hidden="true"></i>{{/is_group}}{{^is_group}}<i class="fas fa-user" aria-hidden="true"></i>{{/is_group}}<span title="{{ uidNumber }}">{{ id }}</span></td><td>{{ full_name }}</td><td>{{ uidNumber }}</td><td>{{#inPosixGroup}}<i class="fas fa-check"></i>{{/inPosixGroup}}</td><td class="collab_admin_actions"></td></tr>{{/collabs}}`;
var actions_tmpl = `<span title="{{#hasrole}}Click to deny {{/hasrole}}{{^hasrole}}Click to grant {{/hasrole}}{{ tooltip }}" data-role-fq-name="{{ rl }}">{{^hasrole}}<i class="fas fa-lg {{ ic }} collab-no-role" aria-hidden="true"></i>{{/hasrole}}
  {{#hasrole}}<span><i class="fas {{ ic }} fa-lg" aria-hidden="true"></i><span class="croxxout">x</span></span>{{/hasrole}}</span>`;
Mustache.parse(collab_tr_tmpl);
Mustache.parse(actions_tmpl);
var refreshFunction = function() {
    $("#collab_tab .collabtbl tbody").empty();
    $.when($.getJSON("ws/collaborators"), $.getJSON("ws/has_role", {"role_fq_name": "LogBook/Manager"}), $.getJSON("ws/exp_posix_group_members"))
    .done(function(d0, d1, d2){
        var collabs = d0[0].value, hasRoleManager = _.get(privileges, "manage_groups", false), posixmembers = d2[0].value;
        _.each(collabs, function(c){
            c["id"] = _.replace(c["uid"], "uid:", "")
            c["inPosixGroup"] = _.includes(posixmembers, c["id"]);
        });
        collabs.sort(function(u1, u2){
            if(u1["is_group"] == u2["is_group"]) { return u1["id"].localeCompare(u2["id"]); }
            if(!u1["is_group"]) { return -1 }
            if(!u2["is_group"]) { return 1 }
        });
        var rendered = $(Mustache.render(collab_tr_tmpl, {collabs: collabs}));
        $("#collab_tab .collabtbl tbody").append(rendered);
        if(hasRoleManager) {
            _.each(collabs, function(collab) {
                _.each([["LogBook/Reader", "fa-book-reader", "permission to read entries"],
                        ["LogBook/Writer", "fa-pencil-alt", "permission to write/post log entries"],
                        ["LogBook/Editor", "fa-edit", "permission to edit/change existing entries"],
                        ["LogBook/Manager", "fa-gavel", "permission to add/remove collaborators"]], function(rl_ic){
                      $("tr[data-uid='" + collab["uid"] + "'] td.collab_admin_actions").append(Mustache.render(actions_tmpl, {rl : rl_ic[0], ic: rl_ic[1], hasrole: _.indexOf(collab.roles, rl_ic[0]) != -1, tooltip: rl_ic[2] }));
                });
                $("tr[data-uid='" + collab["uid"] + "'] td.collab_admin_actions").append($("<span class='remove-collab' title='Remove this user/group from this experiment'><i class='fas fa-lg fa-trash' aria-hidden='true'></i></span>"));
            });
            $("span[data-role-fq-name]").on("click", function(){
                var role_fq_name = $(this).attr("data-role-fq-name"), uid = $(this).closest("tr").attr("data-uid");
                $.getJSON({url: "ws/toggle_role?uid=" + encodeURIComponent(uid) + "&role_fq_name=" + encodeURIComponent(role_fq_name), method: "POST"})
                .done(function() { $("#collab_tab").data("refresh")(); })
                .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); alert("Server side exception adding/removing role " + jqXHR.responseText); })
            });
            $(".remove-collab").on("click", function() {
                var uid = $(this).closest("tr").attr("data-uid");
                $.getJSON({url: "ws/remove_collaborator?uid=" + encodeURIComponent(uid), method: "POST"})
                .done(function() { $("#collab_tab").data("refresh")(); })
                .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); alert("Server side exception removing collaborator " + jqXHR.responseText); })
            })
        }
    });
}

let toolbar_functions = function() {
    if (!_.get(privileges, "manage_groups", false)) { console.log("User is not an admin; skipping actions."); return; }
    var tab_toolbar = `<span id="collab_add_user" title="Add a user to the experiment as a collaborator"><i class="fas fa-user fa-lg"></i></span>
    <span id="collab_add_group" title="Add a user group"><i class="fas fa-users fa-lg"></i></span>
    <span id="collab_sync_user_portal" title="Import collaborators from the user portal"><i class="fas fa-sync fa-lg"></i></span>
    `;
    var uid_search_results = `{{#value}}<tr data-uid="{{ uid }}"><td>{{ uid }}</td><td>{{ gecos }}</td><td><input class="collab_select" type="checkbox"></td></tr>{{/value}}`;
    var group_search_results = `{{#value}}<tr data-uid="{{ . }}"><td>{{ . }}</td><td>N/A</td><td><input class="collab_select" type="checkbox"></td></tr>{{/value}}`;
    Mustache.parse(uid_search_results);
    Mustache.parse(group_search_results);
    var toolbar_rendered = $(tab_toolbar);
    $("#toolbar_for_tab").append(toolbar_rendered);
    var search_and_add = function(search_url, param_name, ms_template, uid_prefix) {
        $.ajax('../../static/html/ms/collab_search_and_add.html')
        .done(function(mdltext) {
            $("#collab_mdl_holder").append(Mustache.render(mdltext, {intromsg: "User/groups are added as players to the Writer role. To give them additional privileges, please use the main matrix"}));
            $("#collab_mdl_holder").find(".collab_search").on("input", delayFunction(function() {
                if($(this).val().length > 2) {
                    var search_params = {}; search_params[param_name] = "*"+$(this).val()+"*";
                    $.getJSON(search_url, search_params)
                    .done(function(data){
                        $("#collab_mdl_holder").find("tbody").empty().append(Mustache.render(ms_template, data));
                    });
                } else{
                    $("#collab_mdl_holder").find("tbody").empty();
                }
            }));
            $("#collab_mdl_holder").find(".edit_modal").on("hidden.bs.modal", function(){
                var add_new_collab_to_role = function(uid, role_fq_name) { return $.getJSON({url: "ws/add_collaborator?uid=" + encodeURIComponent(uid) + "&role_fq_name=" + encodeURIComponent(role_fq_name), method: "POST"}); }
                var ajax_calls = [];
                $("#collab_mdl_holder").find("tbody").find(".collab_select:checked").each(function(){var uid = uid_prefix + $(this).closest("tr").attr("data-uid"); ajax_calls.push(add_new_collab_to_role(uid, "LogBook/Writer"));});
                $.when.apply(this, ajax_calls)
                .done(function() { $(".modal-body").html(""); $("#collab_mdl_holder").empty(); $("#collab_tab").data("refresh")(); })
                .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); error_message("Server side exception adding collaborator " + jqXHR.responseText); })
            });
            $("#collab_mdl_holder").find(".edit_modal").modal("show");
        });
    };

    $("#collab_add_user").on("click", function(){
        search_and_add("../ws/get_matching_uids", "uid", uid_search_results, "uid:");
    });
    $("#collab_add_group").on("click", function(){
        search_and_add("../ws/get_matching_groups", "group_name", group_search_results, "");
    });
    $("#collab_sync_user_portal").on("click", function(){
        $.getJSON("ws/sync_collaborators_with_user_portal")
        .done(function(){ $("#collab_tab").data("refresh")(); })
        .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); error_message("Server side exception syncing with the user portal " + jqXHR.responseText); })
    })
}

export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="collab_tab">
        <div id="collab_mdl_holder"></div>
        <div class="container-fluid text-center" id="collab_content">
            <div class="table-responsive">
                <table class="table table-condensed table-striped table-bordered collabtbl">
                    <thead><tr><th>Id</th><th>Full Name</th><th>UID number</th><th title="Is this user a member of the experiment specific posix group?">Posix Member</th><th>Permissions</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>
    </div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

    $("#collab_tab").data("refresh", refreshFunction);
    refreshFunction();

    toolbar_functions();
}
