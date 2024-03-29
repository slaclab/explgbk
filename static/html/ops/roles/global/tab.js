let thtmpl = `<tr><th>User/Group</th>{{#.}}<th title={{privstr}}>{{name}}</th>{{/.}}</tr>`;
Mustache.parse(thtmpl);
let tbtmpl = `{{#.}}<tr data-player="{{player}}"><td>{{player}}</td>{{#rolchecks}}<td class="role_check {{#hasrole}}ischecked{{/hasrole}}" data-role="{{role}}">{{#hasrole}}<i class="fas fa-check"></i>{{/hasrole}}</td>{{/rolchecks}}</tr>{{/.}}`;
Mustache.parse(tbtmpl);


export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="global_roles_tab">
    <div class="row">
        <div id="glbl_role_mdl_holder"></div>
        <div class="table-responsive">
            <table class="table table-condensed table-striped table-bordered roles_tbl">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    </div>
    `;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

    $.getJSON("../ws/global_roles")
    .done(function(d0){
        let glbl_role_objs = _.sortBy(d0.value, ["name"]), glbl_players = {};
        _.each(glbl_role_objs, function(o){
            o.privstr = _.join(o["privileges"], ",")
            _.each(o.players, function(p){ if (!_.has(glbl_players, p)){ glbl_players[p] = []}; glbl_players[p].push(o.name); });
        })
        let renderedth = $(Mustache.render(thtmpl, glbl_role_objs));
        $("#global_roles_tab").find(".roles_tbl").find("thead").append(renderedth);
        let glbl_players_matrix = _.map(_.keys(glbl_players).sort(), function(p){
            let ret = {player: p, rolchecks: []};
            _.each(glbl_role_objs, function(r){ ret.rolchecks.push({role: r["name"], hasrole: _.includes(glbl_players[p], r["name"]) ? true : false}) });
            return ret;
        });
        let renderedtb = $(Mustache.render(tbtmpl, glbl_players_matrix));
        let add_remove_ug = function(){
            let role_name = $(this).attr("data-role"), isChecked = $(this).hasClass("ischecked"), player = $(this).closest("tr").attr("data-player");
            console.log("Need to " + (isChecked ? "remove" : "add" ) + " " + player + " to/from" + role_name);
            $.getJSON({url: (isChecked ? "../ws/remove_player_from_global_role" : "../ws/add_player_to_global_role" ), method: "POST", data: { role: role_name, player: player }})
            .done(function() { location.reload(); })
            .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); alert("Server side exception " + jqXHR.responseText); })
        }
        renderedtb.find(".role_check").on("click", add_remove_ug);
        $("#global_roles_tab").find(".roles_tbl").find("tbody").append(renderedtb);

        var tab_toolbar = `<span id="glbl_role_add_user" title="Add a user to the list in the UI"><i class="fa-solid fa-user fa-lg"></i></span>
        <span id="glbl_role_add_group" title="Add a user group to the list in the UI."><i class="fa-solid fa-users fa-lg"></i></span>`;
        var uid_search_results = `{{#value}}<tr data-uid="{{ uid }}"><td>{{ uid }}</td><td>{{ gecos }}</td><td><input class="glbl_role_select" type="checkbox"></td></tr>{{/value}}`;
        var group_search_results = `{{#value}}<tr data-uid="{{ . }}"><td>{{ . }}</td><td>N/A</td><td><input class="glbl_role_select" type="checkbox"></td></tr>{{/value}}`;
        Mustache.parse(uid_search_results);
        Mustache.parse(group_search_results);
        var toolbar_rendered = $(tab_toolbar);
        $("#toolbar_for_tab").append(toolbar_rendered);
        var search_and_add = function(search_url, param_name, ms_template, uid_prefix) {
            $.ajax('../../static/html/ms/collab_search_and_add.html')
            .done(function(mdltext) {
                $("#glbl_role_mdl_holder").empty().append(Mustache.render(mdltext, {intromsg: "Users/groups added in this tab inherit privileges for all experiments. For safety, users/groups are not added to roles in the database unless you explicitly add them as a player to one or more roles in the matrix below. First, search for, select and add the user/group to the UI. Then, choose one or more roles for the newly added user/group to play. After you add the first role, the default sort order will kick in and the tab will resort itself by user/group id."}));
                $("#glbl_role_mdl_holder").find(".collab_search").on("input", delayFunction(function() {
                    if($(this).val().length > 2) {
                        var search_params = {}; search_params[param_name] = "*"+$(this).val()+"*";
                        $.getJSON(search_url, search_params)
                        .done(function(data){
                            $("#glbl_role_mdl_holder").find("tbody").empty().append(Mustache.render(ms_template, data));
                        });
                    } else{
                        $("#glbl_role_mdl_holder").find("tbody").empty();
                    }
                }));
                $("#glbl_role_mdl_holder").find(".add_selected").on("click", function(ev){
                    var ugids = [];
                    $("#glbl_role_mdl_holder").find("tbody").find(".glbl_role_select:checked").each(function(){var ugid = uid_prefix + $(this).closest("tr").attr("data-uid"); ugids.push(ugid);});
                    _.each(ugids, function(ug){
                        if(_.includes(_.keys(glbl_players), ug)) { return; }
                        let ugr = $(Mustache.render(tbtmpl, {player: ug, rolchecks: _.map(glbl_role_objs, function(r){ return { role: r.name, hasrole: false }})}));
                        ugr.find(".role_check").on("click", add_remove_ug);
                        $("#global_roles_tab").find(".roles_tbl").find("tbody").prepend(ugr);
                    })
                    $("#glbl_role_mdl_holder").find(".modal").modal("hide");
                });
                $("#glbl_role_mdl_holder").find(".modal").modal("show");
            });
        };

        $("#glbl_role_add_user").on("click", function(){
            search_and_add("../ws/get_matching_uids", "uid", uid_search_results, "uid:");
        });
        $("#glbl_role_add_group").on("click", function(){
            search_and_add("../ws/get_matching_groups", "group_name", group_search_results, "");
        });
    })    
}
