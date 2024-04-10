let thtmpl = `<tr><th>User/Group</th>{{#.}}<th title={{privstr}}>{{name}}</th>{{/.}}</tr>`;
Mustache.parse(thtmpl);
let tbtmpl = `{{#.}}<tr data-player="{{player}}"><td>{{player}}</td>{{#rolchecks}}<td class="role_check {{#hasrole}}ischecked{{/hasrole}}" data-role="{{role}}">{{#hasrole}}<i class="fas fa-check"></i>{{/hasrole}}</td>{{/rolchecks}}</tr>{{/.}}`;
Mustache.parse(tbtmpl);


export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="global_roles_tab">
    <div class="row">
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

    fetch("../ws/global_roles")
    .then((resp) => { return resp.json() })
    .then((d0) => {
        let glbl_role_objs = _.sortBy(d0.value, ["name"]), glbl_players = {};
        _.each(glbl_role_objs, function(o){
            o.privstr = _.join(o["privileges"], ",")
            _.each(o.players, function(p){ if (!_.has(glbl_players, p)){ glbl_players[p] = []}; glbl_players[p].push(o.name); });
        })
        document.querySelector("#global_roles_tab .roles_tbl thead").innerHTML = Mustache.render(thtmpl, glbl_role_objs);
        let glbl_players_matrix = _.map(_.keys(glbl_players).sort(), function(p){
            let ret = {player: p, rolchecks: []};
            _.each(glbl_role_objs, function(r){ ret.rolchecks.push({role: r["name"], hasrole: _.includes(glbl_players[p], r["name"]) ? true : false}) });
            return ret;
        });

        document.querySelector("#global_roles_tab .roles_tbl tbody").innerHTML = Mustache.render(tbtmpl, glbl_players_matrix);
        let add_remove_ug = function(ev){
            let role_name = ev.currentTarget.getAttribute("data-role"), isChecked = ev.currentTarget.classList.contains("ischecked"), player = ev.currentTarget.closest("tr").getAttribute("data-player");
            if(_.isNil(role_name) || _.isNil(player)) { error_message("Bug! Cannot determine role or player"); return; }
            console.log("Need to " + (isChecked ? "remove" : "add" ) + " " + player + " to/from " + role_name);
            postPutJSON((isChecked ? "../ws/remove_player_from_global_role" : "../ws/add_player_to_global_role" ), "POST", { role: role_name, player: player }, () => window.location.reload(), error_message);
        }
        document.querySelectorAll("#global_roles_tab .roles_tbl tbody .role_check").forEach((elem => {elem.addEventListener("click", add_remove_ug)}));

        var tab_toolbar = `<span id="glbl_role_add_user" title="Add a user to the list in the UI"><i class="fa-solid fa-user fa-lg"></i></span>
        <span id="glbl_role_add_group" title="Add a user group to the list in the UI."><i class="fa-solid fa-users fa-lg"></i></span>`;
        var uid_search_results = `{{#value}}<tr data-uid="{{ uid }}"><td>{{ uid }}</td><td>{{ gecos }}</td><td><input class="glbl_role_select" type="checkbox"></td></tr>{{/value}}`;
        var group_search_results = `{{#value}}<tr data-uid="{{ . }}"><td>{{ . }}</td><td>N/A</td><td><input class="glbl_role_select" type="checkbox"></td></tr>{{/value}}`;
        Mustache.parse(uid_search_results);
        Mustache.parse(group_search_results);
        document.querySelector("#toolbar_for_tab").innerHTML = tab_toolbar;
        var search_and_add = function(search_url, param_name, ms_template, uid_prefix) {
            fetch('../../static/html/ms/collab_search_and_add.html')
            .then((resp) => { return resp.text() })
            .then((mdltext) => {
                document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(mdltext, {intromsg: "Users/groups added in this tab inherit privileges for all experiments. For safety, users/groups are not added to roles in the database unless you explicitly add them as a player to one or more roles in the matrix below. First, search for, select and add the user/group to the UI. Then, choose one or more roles for the newly added user/group to play. After you add the first role, the default sort order will kick in and the tab will resort itself by user/group id."});
                const modalElem = document.querySelector("#glbl_modals_go_here .modal");
                modalElem.addEventListener("hidden.bs.modal", () => { document.querySelector("#glbl_modals_go_here").innerHTML = ""; })
                const myModal = new bootstrap.Modal(modalElem);
                myModal.show();

                document.querySelector("#glbl_modals_go_here .collab_search").addEventListener("input", delayFunction(function(ev) {
                    const val = ev.target.value;
                    if(val.length > 2) {
                        const search_params = new URLSearchParams([[param_name, "*"+$(this).val()+"*"]]);
                        fetch(search_url + "?" + search_params.toString())
                        .then((resp) => { return resp.json() })
                        .then((data) => {
                            document.querySelector("#glbl_modals_go_here tbody").innerHTML = Mustache.render(ms_template, data);
                        });
                    } else{
                        document.querySelector("#glbl_modals_go_here tbody").innerHTML = "";
                    }
                }));
                document.querySelector("#glbl_modals_go_here .add_selected").addEventListener("click", function(ev){
                    var ugids = [];
                    document.querySelectorAll("#glbl_modals_go_here tbody .glbl_role_select:checked").forEach(function(elem){
                        var ugid = uid_prefix + elem.closest("tr").getAttribute("data-uid"); 
                        ugids.push(ugid);
                    });
                    _.each(ugids, function(ug){
                        if(_.includes(_.keys(glbl_players), ug)) { return; }
                        let tempelem = document.createElement("tbody");
                        tempelem.innerHTML = Mustache.render(tbtmpl, {player: ug, rolchecks: _.map(glbl_role_objs, function(r){ return { role: r.name, hasrole: false }})});
                        tempelem.querySelectorAll(".role_check").forEach((chk) => { chk.addEventListener("click", add_remove_ug)});
                        document.querySelector("#global_roles_tab .roles_tbl tbody").prepend(tempelem.firstChild);
                    })
                    myModal.hide();
                });
            });
        };

        document.querySelector("#glbl_role_add_user").addEventListener("click", function(){
            search_and_add("../ws/get_matching_uids", "uid", uid_search_results, "uid:");
        });
        document.querySelector("#glbl_role_add_group").addEventListener("click", function(){
            search_and_add("../ws/get_matching_groups", "group_name", group_search_results, "");
        });
    })    
}
