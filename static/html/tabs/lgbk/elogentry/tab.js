let elog_main_template = `<div class="edat row col-12" id="{{ elem_id }}">
<div class="row col-12">
 <div class="card">
  <div class="card-header text-start">
     {{#title}}<div class="chid_title{{#deleted_by}}elog_deleted{{/deleted_by}}">{{title}}</div>{{/title}}
     <div class="row">
       <div class="col-2">{{#FormatDate}}{{ relevance_time }}{{/FormatDate}}</div>
       <div class="col-1" title="{{run_num}}">{{ run_num_str }}</div>
       <div class="col-5 elog_main_cnt text_truncate {{#deleted_by}}elog_deleted{{/deleted_by}} ">{{#title}}{{title}}<div class="chid_content">{{{content}}}</div>{{/title}}{{^title}}<pre class="precontent">{{ content }}</pre>{{/title}}</div><div class="col-3 elog_main_cnt">{{#src_expname}}{{.}}{{#tagcount}}|{{/tagcount}}{{/src_expname}}{{#tags}}<span class="elog_tag">{{.}}</span>{{/tags}}</div>
       <div class="col-1">{{ author }}</div>
     </div>
   </div>
  <div class="card-body">
    <div class="elog_chid_body_content">{{#deleted_by}}<div class="row elog_deleted_by">Deleted by {{deleted_by}} - {{#FormatDate}}{{ deleted_time }}{{/FormatDate}}</div>{{/deleted_by}}
    <div class="row">{{#attachments}}<div class="col-3"><a href="../ws/attachment?entry_id={{entry_id}}&attachment_id={{_id}}&prefer_preview=False" target="_blank" class="thumbnail"><img class="elog_img" src="../ws/attachment?entry_id={{entry_id}}&attachment_id={{_id}}&prefer_preview=true"></img></a></div>{{/attachments}}</div></div>
  </div>
  </div>
 </div>
 </div>`;

 Mustache.parse(elog_main_template);
 
 let truncateMiddle = function(x) {
    let strv = _.toString(x);
    if (strv.length > 10) {
        return strv.substr(0,5) + "..." +  strv.substr(strv.length-5);
    }
    return strv;
}

let processElogEntry = function(entry) {
    let root = _.get(entry, "root", null), parent = _.get(entry, "parent", null), attachments = _.get(entry, "attachments", null);
    if(attachments != null) {
        entry["c_attach"] = true;
        _.each(attachments, function(attachment) { attachment["entry_id"] = entry["_id"]; });
    }
    entry["run_num_str"] = truncateMiddle(entry["run_num"]);
    // entry.expandFunction = expandFunction;
    entry["elem_id"] = entry["_id"];
    entry["r_time"] = (new Date(entry["relevance_time"])).getTime();
    entry["emails_str"] = _.join(_.get(entry, "email_to", []), " ");
}

let attach_children = function(entries) {
    let id2entry = _.keyBy(entries, "_id");
    _.each(id2entry, function(entry, key){
        let myid = entry["_id"], root = _.get(entry, "root", null), parent = _.get(entry, "parent", null);
        if(parent != null && _.has(id2entry, parent)) {
            let pey = id2entry[parent];
                _.defaults(pey, {"c_children": []});
                pey["c_children"] = _.union(pey["c_children"], [ entry["_id"] ]);
        }
        if(root != null && _.has(id2entry, root)) {
            let rey = id2entry[root];
                _.defaults(rey, {"c_desc": []});
                rey["c_desc"] = _.union(rey["c_desc"], [ entry["_id"] ]);
        }
    });
}

let renderElogResponse = function(entries) {
    _.each(entries, function(entry){
        entry.FormatDate = elog_formatdatetime;
        let rendered = Mustache.render(elog_main_template, entry);
        if(_.has(entry, "parent")) {
            if($("#"+entry["parent"]).length > 0) {
                $("#"+entry["parent"]).find(".elog_chid_body_content").first().append(rendered);
            } else {
                error_message("Missing parent id for elog " + entry["parent"]);
            }
        } else {
            $("#elog_sgl_entry").append(rendered);
        }
    })
}

let processElogResponse = function(entries) {
    _.each(entries, function(entry) { processElogEntry(entry); });
    attach_children(entries);
    let root_entry = _.find(entries, function(x){ return !_.has(x, "parent");})
    if(!root_entry) { error_message("Cannot find root entry"); return;}
    // Breadth first from root_entry
    let bfls = [ root_entry ], ret = [], id2entry = _.keyBy(entries, "_id");;
    while(bfls.length > 0) {
        let n = bfls.shift();
        ret.push(n);
        _.each(_.get(n, "c_children", []), function(c) { bfls.push(id2entry[c]); })
        console.log(bfls.length);
    }
    return ret;
};

export function tabshow() {
    $.getJSON({ url: "../ws/elog/" + entry_id + "/complete_elog_tree"}).done(function(data){
        let entries = processElogResponse(data.value);
        renderElogResponse(entries);
        $("#toolbar_for_tab").find(".syncelog").on("click", function(){
            sessionStorage.setItem("eLog_scrollTo", entries[0]["_id"]);
            window.location.href = "../eLog";
        })
    })    
}

