let thtmpl = `<tr><th>User/Group</th>{{#.}}<th title={{privstr}}>{{name}}</th>{{/.}}</tr>`;
Mustache.parse(thtmpl);
let tbtmpl = `{{#.}}<tr data-player="{{player}}"><td>{{player}}</td>{{#rolchecks}}<td class="role_check {{#hasrole}}ischecked{{/hasrole}}" data-role="{{role}}">{{#hasrole}}<i class="fas fa-check"></i>{{/hasrole}}</td>{{/rolchecks}}</tr>{{/.}}`;
Mustache.parse(tbtmpl);
let insseltmpl = `<span class="col-3 input-group-text mx-0">Instrument level permissions for:</span><span class="col-2"><select class="form-select choose_instr">{{#.}}<option value="{{_id}}" {{#selected}}selected{{/selected}}>{{_id}}</option>{{/.}}</select></span>`;
Mustache.parse(insseltmpl);


let glbl_role_objs = {}, inst_players = [];

let add_remove_ug = function(ev){    
    let ins = document.querySelector("#inst_roles_tab .choose_instr").value;
    let role_name = ev.currentTarget.getAttribute("data-role");
    let isChecked = ev.currentTarget.classList.contains("ischecked");
    let player = ev.currentTarget.closest("tr").getAttribute("data-player");
    console.log("Need to " + (isChecked ? "remove" : "add" ) + " " + player + " to/from " + role_name);
    postPutJSON((isChecked ? "../ws/remove_player_from_instrument_role" : "../ws/add_player_to_instrument_role" ), "POST", { instrument: ins, role: role_name, player: player }, () => {localStorage.setItem("lgbk/ops/insroles/currins", ins); window.location.reload()}, error_message);
}

let change_ins = function() {
    fetch("../ws/instruments")
    .then((resp) => { return resp.json() })
    .then((d0) => {
        let instrs = d0.value;
        inst_players = _.uniq(_.flatten(_.map(_.flatten(_.reject(_.map(instrs, "roles"), _.isNil)), "players"))).sort();
        _.each(instrs, function(i){
            i.inst_players_matrix = _.map(inst_players, function(p){
                let ret = { player: p, rolchecks: [] };
                _.each(_.map(glbl_role_objs, "name"), function(r){ ret.rolchecks.push({role: r, hasrole: _.includes(_.get(_.find(_.get(i, "roles", []), ["name", r]), "players", []), p) ? true : false}) });
                return ret;
            });
        })
        let ins = document.querySelector("#inst_roles_tab .choose_instr").value, chins = _.find(instrs, ["_id", ins]);
        document.querySelector("#inst_roles_tab .roles_tbl tbody").innerHTML = Mustache.render(tbtmpl, chins.inst_players_matrix);
        document.querySelectorAll("#inst_roles_tab .roles_tbl tbody .role_check").forEach((elem) => { elem.addEventListener("click", add_remove_ug)});
    })
}


export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="inst_roles_tab">
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

    Promise.all([fetch("../ws/instruments"), fetch("../ws/global_roles")])
    .then((resps) => { return Promise.all([resps[0].json(), resps[1].json()])})
    .then((vals) => {
        let [ d0, d1 ] = vals;
        glbl_role_objs = _.sortBy(d1.value, ["name"]);
        let instruments = d0.value;
        let previously_shown_ins = localStorage.getItem("lgbk/ops/insroles/currins");
        if(!_.isNil(previously_shown_ins)) {
            _.set(_.find(instruments, ["_id", previously_shown_ins]), "selected", true);
            localStorage.removeItem("lgbk/ops/insroles/currins")
        }
        document.querySelector("#inst_roles_tab .inshdr").innerHTML = Mustache.render(insseltmpl, instruments);
        _.each(glbl_role_objs, function(o){ o.privstr = _.join(o["privileges"], ",") })
        document.querySelector("#inst_roles_tab .roles_tbl thead").innerHTML = Mustache.render(thtmpl, glbl_role_objs);
        document.querySelector("#inst_roles_tab .choose_instr").addEventListener("change", change_ins);
        change_ins();
        
        const tab_toolbar = `<span id="inst_role_add_user" title="Add a user to the list in the UI"><i class="fas fa-user fa-lg"></i></span><span id="inst_role_add_group" title="Add a user group to the list in the UI."><i class="fas fa-users fa-lg"></i></span>`;
        const uid_search_results = `{{#value}}<tr data-uid="{{ uid }}"><td>{{ uid }}</td><td>{{ gecos }}</td><td><input class="inst_role_select" type="checkbox"></td></tr>{{/value}}`;
        const group_search_results = `{{#value}}<tr data-uid="{{ . }}"><td>{{ . }}</td><td>N/A</td><td><input class="inst_role_select" type="checkbox"></td></tr>{{/value}}`;
        Mustache.parse(uid_search_results);
        Mustache.parse(group_search_results);
        document.querySelector("#toolbar_for_tab").innerHTML = tab_toolbar;
        
        const search_and_add = function(search_url, param_name, ms_template, uid_prefix) {
            fetch('../../static/html/ms/collab_search_and_add.html')
            .then((resp) => { return resp.text() })
            .then((mdltext) => {
                document.querySelector("#glbl_modals_go_here").innerHTML = Mustache.render(mdltext, {intromsg: "Users/groups added in this tab inherit privileges for all experiments in this instrument. For safety, users/groups are not added to roles in the database unless you explicitly add them as a player to one or more roles in the matrix below. First, search for, select and add the user/group to the UI. Then, choose one or more roles for the newly added user/group to play. After you add the first role, the default sort order will kick in and the tab will resort itself by user/group id."});
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
                        })
                    } else{
                        document.querySelector("#glbl_modals_go_here tbody").innerHTML = "";
                    }
                }));
                document.querySelectorAll("#glbl_modals_go_here .add_selected").forEach((elem) => { elem.addEventListener("click", function(ev) {
                    const ugids = [];
                    document.querySelectorAll("#glbl_modals_go_here tbody .inst_role_select:checked").forEach(function(elem){
                        var ugid = uid_prefix + elem.closest("tr").getAttribute("data-uid"); 
                        ugids.push(ugid);
                    });
                    _.each(ugids, function(ug){
                        if(_.includes(inst_players, ug)) { return; }
                        let tempelem = document.createElement("tbody");
                        tempelem.innerHTML = Mustache.render(tbtmpl, {player: ug, rolchecks: _.map(glbl_role_objs, function(r){ return { role: r.name, hasrole: false }})});
                        tempelem.querySelectorAll(".role_check").forEach((chk) => { chk.addEventListener("click", add_remove_ug)});
                        document.querySelector("#inst_roles_tab .roles_tbl tbody").prepend(tempelem.firstChild);
                    })
                    myModal.hide();
                })});
            });
        };

        document.querySelector("#inst_role_add_user").addEventListener("click", function(){
            search_and_add("../ws/get_matching_uids", "uid", uid_search_results, "uid:");
        });
        document.querySelector("#inst_role_add_group").addEventListener("click", function(){
            search_and_add("../ws/get_matching_groups", "group_name", group_search_results, "");
        });
    })
}
