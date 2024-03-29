let thtmpl = `<tr><th>User/Group</th>{{#.}}<th title={{privstr}}>{{name}}</th>{{/.}}</tr>`;
Mustache.parse(thtmpl);
let tbtmpl = `{{#.}}<tr data-player="{{player}}"><td>{{player}}</td>{{#rolchecks}}<td class="role_check {{#hasrole}}ischecked{{/hasrole}}" data-role="{{role}}">{{#hasrole}}<i class="fas fa-check"></i>{{/hasrole}}</td>{{/rolchecks}}</tr>{{/.}}`;
Mustache.parse(tbtmpl);
let insseltmpl = `<span class="col-3 input-group-text mx-0">Instrument level permissions for:</span><span class="col-2"><select class="form-select choose_instr">{{#.}}<option value="{{_id}}">{{_id}}</option>{{/.}}</select></span>`;
Mustache.parse(insseltmpl);


let glbl_role_objs = {}, glbl_players = {}, inst_players = [];

let add_remove_ug = function(){
    let ins = $("#inst_roles_tab").find(".choose_instr").val(), role_name = $(this).attr("data-role"), isChecked = $(this).hasClass("ischecked"), player = $(this).closest("tr").attr("data-player");
    console.log("Need to " + (isChecked ? "remove" : "add" ) + " " + player + " to/from" + role_name);
    $.getJSON({url: (isChecked ? "../ws/remove_player_from_instrument_role" : "../ws/add_player_to_instrument_role" ), method: "POST", data: { instrument: ins, role: role_name, player: player }})
    .done(function() { $("#inst_roles_tab").trigger("insref"); })
    .fail(function(jqXHR, textStatus, errorThrown) { console.log(jqXHR); alert("Server side exception " + jqXHR.responseText); })
}

let change_ins = function() {
    $.getJSON("../ws/instruments")
    .done(function(d0){
        let instrs = d0.value;
        inst_players = _.uniq(_.flatten(_.map(_.flatten(_.reject(_.map(instrs, "roles"), _.isNil)), "players"))).sort();
        _.each(instrs, function(i){
            i.inst_players_matrix = _.map(inst_players, function(p){
                let ret = { player: p, rolchecks: [] };
                _.each(_.map(glbl_role_objs, "name"), function(r){ ret.rolchecks.push({role: r, hasrole: _.includes(_.get(_.find(_.get(i, "roles", []), ["name", r]), "players", []), p) ? true : false}) });
                return ret;
            });
        })
        let ins = $("#inst_roles_tab").find(".choose_instr").val(), chins = _.find(instrs, ["_id", ins]);
        let renderedtb = $(Mustache.render(tbtmpl, chins.inst_players_matrix));
        renderedtb.find(".role_check").on("click", add_remove_ug);
        $("#inst_roles_tab").find(".roles_tbl").find("tbody").empty().append(renderedtb);
    })
}


export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="inst_roles_tab">
    <div id="inst_role_mdl_holder"></div>
    <div class="row input-group inshdr">
    </div>
    <div class="row">
        <div class="table-responsive">
            <table class="table table-condensed table-striped table-bordered roles_tbl">
                <thead></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    </div>`;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;

    $.when($.getJSON("../ws/instruments"), $.getJSON("../ws/global_roles"))
    .done(function(d0, d1){
        glbl_role_objs = _.sortBy(d1[0].value, ["name"]);
        let renderinssel = $(Mustache.render(insseltmpl, d0[0].value));
        $("#inst_roles_tab .inshdr").empty().append(renderinssel);
        _.each(glbl_role_objs, function(o){ o.privstr = _.join(o["privileges"], ",") })
        let renderedth = $(Mustache.render(thtmpl, glbl_role_objs));
        $("#inst_roles_tab").find(".roles_tbl").find("thead").append(renderedth);

        $("#inst_roles_tab").find(".choose_instr").on("change", change_ins);
        $("#inst_roles_tab").on("insref", change_ins);
        $("#inst_roles_tab").trigger("insref");

        var tab_toolbar = `<span id="inst_role_add_user" title="Add a user to the list in the UI"><i class="fas fa-user fa-lg"></i></span>
        <span id="inst_role_add_group" title="Add a user group to the list in the UI."><i class="fas fa-users fa-lg"></i></span>`;
        var uid_search_results = `{{#value}}<tr data-uid="{{ uid }}"><td>{{ uid }}</td><td>{{ gecos }}</td><td><input class="inst_role_select" type="checkbox"></td></tr>{{/value}}`;
        var group_search_results = `{{#value}}<tr data-uid="{{ . }}"><td>{{ . }}</td><td>N/A</td><td><input class="inst_role_select" type="checkbox"></td></tr>{{/value}}`;
        Mustache.parse(uid_search_results);
        Mustache.parse(group_search_results);
        var toolbar_rendered = $(tab_toolbar);
        $("#toolbar_for_tab").append(toolbar_rendered);
        var search_and_add = function(search_url, param_name, ms_template, uid_prefix) {
            $.ajax('../../static/html/ms/collab_search_and_add.html')
            .done(function(mdltext) {
                $("#inst_role_mdl_holder").empty().append(Mustache.render(mdltext, {intromsg: "Users/groups added in this tab inherit privileges for all experiments in this instrument. For safety, users/groups are not added to roles in the database unless you explicitly add them as a player to one or more roles in the matrix below. First, search for, select and add the user/group to the UI. Then, choose one or more roles for the newly added user/group to play. After you add the first role, the default sort order will kick in and the tab will resort itself by user/group id."}));
                $("#inst_role_mdl_holder").find(".collab_search").on("input", delayFunction(function() {
                    if($(this).val().length > 2) {
                        var search_params = {}; search_params[param_name] = "*"+$(this).val()+"*";
                        $.getJSON(search_url, search_params)
                        .done(function(data){
                            $("#inst_role_mdl_holder").find("tbody").empty().append(Mustache.render(ms_template, data));
                        });
                    } else{
                        $("#inst_role_mdl_holder").find("tbody").empty();
                    }
                }));
                $("#inst_role_mdl_holder").find(".add_selected").on("click", function(ev){
                    var ugids = [];
                    $("#inst_role_mdl_holder").find("tbody").find(".inst_role_select:checked").each(function(){var ugid = uid_prefix + $(this).closest("tr").attr("data-uid"); ugids.push(ugid);});
                    _.each(ugids, function(ug){
                        if(_.includes(inst_players, ug)) { return; }
                        let ugr = $(Mustache.render(tbtmpl, {player: ug, rolchecks: _.map(glbl_role_objs, function(r){ return { role: r.name, hasrole: false }})}));
                        ugr.find(".role_check").on("click", add_remove_ug);
                        $("#inst_roles_tab").find(".roles_tbl").find("tbody").prepend(ugr);
                    })
                    $("#inst_role_mdl_holder").find(".edit_modal").modal("hide");
                });
                $("#inst_role_mdl_holder").find(".edit_modal").modal("show");
            });
        };

        $("#inst_role_add_user").on("click", function(){
            search_and_add("../ws/get_matching_uids", "uid", uid_search_results, "uid:");
        });
        $("#inst_role_add_group").on("click", function(){
            search_and_add("../ws/get_matching_groups", "group_name", group_search_results, "");
        });
    })
}
