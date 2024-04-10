let filterAndGenTrace = function(exp_stats, cutoff, name, attr, xaxis, yaxis) {
    let filterfn = function(s) { return moment(s["_id"]).isAfter(cutoff); }
    let filteredData = _.filter(exp_stats.value, filterfn);
    let trace = { type: 'scatter', name: name, x: _.map(filteredData, function(s) { return moment(s["_id"]).toDate(); }), y: _.map(filteredData, attr), xaxis: xaxis,yaxis: yaxis};
    return trace;
}

let plotDataMovement = function() {
    const report_type = document.querySelector("#ops_reports_tab .inshdr .report_type").value;
    const inssel = document.querySelector("#ops_reports_tab .inshdr .choose_instr").value;
    console.log("Plotting data movement for", inssel, report_type);

    const urlparams = new URLSearchParams([["report_type", report_type], ["instrument", inssel]]);
    fetch("../ws/experiment_daily_data_breakdown?"+urlparams.toString())
    .then((resp) => { return resp.json() })
    .then((exp_stats) => {
        if(report_type == "file_sizes") {
            let allTr = { type: 'scatter', name: "Lifetime", x: _.map(exp_stats.value, function(s) { return moment(s["_id"]).toDate(); }), y: _.map(exp_stats.value, "total_size")},
               lastYearTr = filterAndGenTrace(exp_stats, moment().subtract(1, 'year'), "Last Year", "total_size", "x2", "y2"),
               lastMonthTr = filterAndGenTrace(exp_stats, moment().subtract(1, 'month'), "Last Month", "total_size", "x3", "y3");

               import(lgbkabspath("/js/plotly.js/dist/plotly.min.js")).then((mod) => {
                Plotly.newPlot("dataChart", [lastMonthTr, lastYearTr, allTr],
                    { grid: { rows: 3, columns: 1, pattern: 'independent', roworder: 'bottom to top'},
                    yaxis: {title: "Data (in TB)"}, yaxis2: {title: "Data (in TB)"}, yaxis3: {title: "Data (in TB)"}}
                );
               })
        } else if (report_type == "run_counts") {
            let allTr = { type: 'scatter', name: "Lifetime", x: _.map(exp_stats.value, function(s) { return moment(s["_id"]).toDate(); }), y: _.map(exp_stats.value, "total_runs")},
               lastYearTr = filterAndGenTrace(exp_stats, moment().subtract(1, 'year'), "Last Year", "total_runs", "x2", "y2"),
               lastMonthTr = filterAndGenTrace(exp_stats, moment().subtract(1, 'month'), "Last Month", "total_runs", "x3", "y3");

               import(lgbkabspath("/js/plotly.js/dist/plotly.min.js")).then((mod) => {
                Plotly.newPlot("dataChart", [lastMonthTr, lastYearTr, allTr],
                    { grid: { rows: 3, columns: 1, pattern: 'independent', roworder: 'bottom to top'},
                    yaxis: {title: "Run count"}, yaxis2: {title: "Run count"}, yaxis3: {title: "Run count"}});
                });
        }
    })
}


export function tabshow(target) {
    const tabpanetmpl = `<div class="container-fluid text-center tabcontainer" id="ops_reports_tab">
    <div class="row inshdr form-group form-inline"></div>
    <div class="row chartrow" id="dataChart">
    </div>
    </div>
    `;
    let trgtname = target.getAttribute("data-bs-target"), trgt = document.querySelector(trgtname); 
    trgt.innerHTML=tabpanetmpl;
    fetch("../ws/instruments")
    .then((resp) => { return resp.json() })
    .then((instruments) => {
        let insseltmpl = `<div><span class="sellabel">Plot</span><select class="custom-select report_type"><option value="file_sizes">File Sizes</option><option value="run_counts">Run Counts</option></select> for <select class="custom-select choose_instr"><option value="ALL">ALL</option>{{#.}}<option value="{{_id}}">{{_id}}</option>{{/.}}</select></div>`; Mustache.parse(insseltmpl);
        document.querySelector("#ops_reports_tab .inshdr").innerHTML = Mustache.render(insseltmpl, instruments.value);
        document.querySelector("#ops_reports_tab .inshdr .choose_instr").addEventListener("change", function() {
            plotDataMovement();
        })
        document.querySelector("#ops_reports_tab .inshdr .report_type").addEventListener("change", function() {
            plotDataMovement();
        })
        plotDataMovement();
    });
}
