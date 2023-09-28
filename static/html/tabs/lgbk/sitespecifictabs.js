export async function loadSiteSpecificTabs(){
    await fetch(new Request('../../static/json/sitespecific_tabs_' + logbook_site + ".json"))
    .then((resp) => {
        if(!resp.ok) { return Promise.reject(new Error("No site specific tabs")); }
        return resp.json()
    })
    .then((tabs) => { 
        var ssnavtmpl = `{{#.}}
        {{^dropdown}}
            <li class="nav-item"><a class="nav-link {{class}}" data-bs-toggle="tab" data-lg-url="{{data-lg-url}}" role="tab" data-bs-target="#{{id}}">{{label}}</a></li>
        {{/dropdown}}
        {{#dropdown}}
            <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" data-bs-toggle="dropdown" href="#" role="button" aria-expanded="false">{{label}}</a>
                <ul class="dropdown-menu">
                {{#submenu}}
                    <li><a class="dropdown-item" data-bs-toggle="tab" data-lg-url="{{data-lg-url}}" role="tab" data-bs-target="#{{id}}">{{label}}</a></li>
                {{/submenu}}
                </ul>
            </li>{{/dropdown}}{{/.}}`;
        var ssnavpnltmpl = `{{#.}}{{^dropdown}}<div role="tabpanel" class="tab-pane fade {{class}}" id="{{id}}"></div>{{/dropdown}}
        {{#dropdown}}{{#submenu}}<div role="tabpanel" class="tab-pane fade" id="{{id}}"></div>{{/submenu}}{{/dropdown}}{{/.}}`;
        Mustache.parse(ssnavtmpl); Mustache.parse(ssnavpnltmpl);
        $("#myNavbar").find(".sitespecific").before(Mustache.render(ssnavtmpl, tabs));
        $("#myTabContainer").find(".sitespecific").before(Mustache.render(ssnavpnltmpl, tabs));
    })
    .catch((errmsg) => { console.log(errmsg) });
}

