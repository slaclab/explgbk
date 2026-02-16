// See docs/pagination.html for more details.
var sortable_paginator = function(container, key_attr, sort_attr, sort_desc=false, page_start=0, page_end=2000, page_size=100) {
    container.data("spgntr", {
        objs: {},
        sorted_objs: [],
        disp_objs: [],
        container: container,
        key_attr: key_attr,
        sort_attr: sort_attr,
        sort_desc: sort_desc,
        page_start: page_start,
        page_end: page_end,
        page_size: page_size
    });
    container.data("spgntr").addObjects = function(objs) {
        if(this.sorted_objs.length == 0) {
            var ap2c = this.container.find(".spgntr_append");
            ap2c.empty();
            this.container.trigger("empty_and_initialize");
            this.sorted_objs = _.sortBy(objs, this.sort_attr);
            this.objs = _.keyBy(objs, this.key_attr);
            this.disp_objs = this.sort_desc ? this.sorted_objs.slice().reverse() : this.sorted_objs;
            var spg = this;
            let elems2insert = [];
            _.each(_.slice(this.disp_objs, this.page_start, this.page_end), function(o, i, c) { elems2insert.push(o.render()); });
            ap2c.append(elems2insert);
        } else {
            _.each(objs, function(obj){ this.addObject(obj)});
        }
    }

    container.data("spgntr").addObject = function(obj) {
        var ap2c = this.container.find(".spgntr_append");
        if(this.sorted_objs.length == 0) {
            ap2c.empty();
            this.container.trigger("empty_and_initialize");
            this.sorted_objs.push(obj);
            this.objs[obj[this.key_attr]] = obj;
            ap2c.append(obj.render());
        } else {
            if(obj[this.key_attr] in this.objs) {
                this.objs[obj[this.key_attr]] = obj;
                this.sorted_objs[_.findIndex(this.sorted_objs, [this.key_attr, obj[this.key_attr]])] = obj;
                this.disp_objs = this.sort_desc ? this.sorted_objs.slice().reverse() : this.sorted_objs;
                var exis_ui_elems = ap2c.find("[data-spgntr="+[obj[this.key_attr]]+"]");
                if(exis_ui_elems.length >= 1) {
                    exis_ui_elems.replaceWith(obj.render());
                }
                return;
            }
            var insertAt = _.sortedIndexBy(this.sorted_objs, obj, this.sort_attr);
            this.sorted_objs.splice(insertAt, 0, obj);
            this.objs[obj[this.key_attr]] = obj;
            this.disp_objs = this.sort_desc ? this.sorted_objs.slice().reverse() : this.sorted_objs;
            var exis_ui_elems = ap2c.find("[data-spgntr="+[obj[this.key_attr]]+"]");
            if(exis_ui_elems.length >= 1) {
                exis_ui_elems.replaceWith(obj.render());
            } else {
                let loc = _.findIndex(this.disp_objs, [this.key_attr, obj[this.key_attr]]);
                if(loc >= this.page_start && loc <= this.page_end) {
                    if(loc >= 0 && loc < this.disp_objs.length) {
                        let ap_a = ap2c.find("[data-spgntr="+ this.disp_objs[loc+1][this.key_attr] +"]");
                        if (ap_a.length >= 1) {
                            ap_a.before(obj.render());
                            this.page_end = this.page_end + 1;
                            return;
                        } else {
                            console.log("Cannot find element to insert before location " + loc + " - [data-spgntr=" + this.disp_objs[loc+1][this.key_attr] + "]");
                        }
                    }
                    if (loc > 0 && loc <= this.disp_objs.length) {
                        let ap_a = ap2c.find("[data-spgntr="+ this.disp_objs[loc-1][this.key_attr] +"]");
                        if (ap_a.length >= 1) {
                            ap_a.after(obj.render());
                            this.page_end = this.page_end + 1;
                            return;
                        } else {
                            console.log("Cannot find element to insert after location " + loc + " - [data-spgntr=" + this.disp_objs[loc-1][this.key_attr] + "]");
                        }
                    }
                    console.log("Cannot determine where to insert " + obj[this.key_attr] + " Location: " + loc + " Array length " + this.disp_objs.length);
                }
            }
        }
    }
    container.data("spgntr").pageDown = function() {
        let prev_page_end = this.page_end, ap2c = this.container.find(".spgntr_append");
        this.page_end = this.page_end + this.page_size;
        console.log("Paging down from " + prev_page_end + " to " + this.page_end);
        let elems2insert = [];
        _.each(_.slice(this.disp_objs, prev_page_end, this.page_end), function(obj){ elems2insert.push(obj.render())});
        ap2c.append(elems2insert);
    }

    container.data("spgntr").scrollTo = function(scrollToId) {
        let prev_page_end = this.page_end, ap2c = this.container.find(".spgntr_append"), scIndex = _.findIndex(this.disp_objs, [key_attr, scrollToId]);
        if(scIndex < 0) { error_message("Cannot find element to scroll to " + scrollToId); }
        if(scIndex < this.page_end) { ap2c.find("[data-spgntr=" + scrollToId + "]")[0].scrollIntoView(); }
        this.page_end = scIndex + 1;
        let elems2insert = [];
        _.each(_.slice(this.disp_objs, prev_page_end, this.page_end), function(obj){ elems2insert.push(obj.render())});
        ap2c.append(elems2insert);
        if(ap2c.find("[data-spgntr=" + scrollToId + "]").length > 0){
            ap2c.find("[data-spgntr=" + scrollToId + "]")[0].scrollIntoView();
        } else {
            error_message("Cannot find DOM element to scroll to " + scrollToId);
        }
    }

    container.data("spgntr").redraw = function() {
        let elems2insert = [], ap2c = this.container.find(".spgntr_append");
        _.each(_.slice(this.disp_objs, this.page_start, this.page_end), function(obj){ elems2insert.push(obj.render())});
        ap2c.empty().append(elems2insert);
    }
}
