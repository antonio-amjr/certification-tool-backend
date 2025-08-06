/**
 *
 * Copyright (c) 2023 Project CHIP Authors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
const margin = { top: 20, right: 20, bottom: 30, left: 90 };
let zoom_value = 10
let zoom_refactor_val = 10
var dataElement = document.getElementById('data');
const summary_json = JSON.parse(dataElement.textContent || dataElement.innerText);
const graph_option_selector_container = document.getElementById("graph_option_selector_container");
let analytics_parameters = Object.keys(summary_json["analytics"])
console.log("hiii")
function reloadSingleCSS(id) {
  const link = document.getElementById(id);
  if (link) {
    const href = link.getAttribute("href").split("?")[0]; // strip old cache buster
    link.setAttribute("href", `${href}?v=${Date.now()}`); // add new timestamp
  }

}

analytics_parameters.forEach(analytics => {
const label = document.createElement("label");
label.className = "dropdown-option";
const checkbox = document.createElement("input");
checkbox.type = "checkbox";
checkbox.id = `checkbox_${analytics}`;
checkbox.value = analytics;
checkbox.onchange = () => capture_display_graph(`checkbox_${analytics}`);
label.appendChild(checkbox);
label.appendChild(document.createTextNode(analytics.toUpperCase()));
graph_option_selector_container.appendChild(label);
});

reloadSingleCSS("graph-css");
document.querySelector("#graph_line_selector").onchange = function () { build_graph() }
function resetGraph() {
    const divElements = document.querySelectorAll('.graph_styling');
    // Loop through the div elements and clear their contents
    divElements.forEach((div) => {
        div.remove();
    });
}
function svg_node_builder(summary_json, analytics_parameter) {
    var width = window.innerWidth - margin.left - margin.right;
    var height = 900;
    let analytics_parameter_data = summary_json["analytics"][analytics_parameter]
    let keys = Object.keys(analytics_parameter_data)
    let values = Object.values(analytics_parameter_data)
    const data = []
    for (i = 0; i < keys.length; i++) {
        if (values[i] != null){
        data.push({ x: keys[i], y: values[i] })
        }
        else{
            data.push({ x: keys[i], y: 0, "error_rectify_msg": "Value was defaulted to zero since non-numeric value was encountered" })
        }
    }
    let x = d3.scaleLinear()
        .domain([0, summary_json["test_summary_record"]["total_number_of_iterations"]])
        .range([margin.left, width - margin.right]);

    let y = d3.scaleLinear()
        .domain([0, Math.max(...values) + 10])
        .range([height - margin.bottom, margin.top]);

    let line = "";
    let graph_selector = document.getElementById("graph_line_selector").value
    switch (graph_selector) {
        case "step_graph":
            line = d3.line()
                .x(d => x(d.x))
                .y(d => y(d.y))
                .curve(d3.curveStep);
            break;
        case "curved_line":
            line = d3.line()
                .x(d => x(d.x))
                .y(d => y(d.y))
                .curve(d3.curveCatmullRom.alpha(0.5));
            break;
        default:
            line = d3.line()
                .x(d => x(d.x))
                .y(d => y(d.y))
                .curve(d3.curveStep);
            break;
    }

    let svg = d3.create("svg")
        .attr("width", "100%")
        .attr("height", height);
    // Add zoom functionality
    let zoom = d3.zoom()
        .scaleExtent([1, 100])
        .on("zoom", zoomed);

    let tooltip = d3.select("#container").append("div")
        .attr("class", "tooltip")
        .style("opacity", 0)
        .style("background-color", "white")
        .style("border", "solid")
        .style("border-width", "2px")
        .style("border-radius", "5px")
        .style("padding", "5px")
        .style("position", "absolute");

    svg.append("g")
        .attr("class", "x-axis")
        .attr("transform", `translate(0,${height - margin.bottom})`)
        .style("font", "bold")
        .style("overflow", "auto")
        .call(d3.axisBottom(x));

    svg.append("g")
        .attr("class", "y-axis")
        .style("overflow", "auto")
        .attr("transform", `translate(${margin.left},0)`)
        .call(d3.axisLeft(y));

    svg.append("path")
        .datum(data)
        .attr("class", "line")
        .attr("fill", "none")
        .attr("stroke", "steelblue")
        .attr("stroke-width", 2)
        .attr("d", line);
    svg.selectAll(".plot-point")  // Correct class selector
        .data(data)
        .enter()
        .append("circle")
        .attr("class", "plot-point")  // Assign a class to the circles
        .attr("fill", "red")
        .attr("stroke", "none")
        .attr("cx", function (d) { return x(d.x) })
        .attr("cy", function (d) { return y(d.y) })
        .attr("r", 4)
        .on("mouseover", handleMouseOver)
        .on("mouseout", handleMouseOut);

    svg.call(zoom);

    function zoomed(event) {
        const newXScale = event.transform.rescaleX(x);
        const newYScale = event.transform.rescaleY(y);
        svg.select(".x-axis").call(d3.axisBottom(newXScale));
        svg.select(".line").attr("d", line.x(d => newXScale(d.x))
            .y(d => newYScale(d.y)));
        updateZoomLevel(event.transform.k);
        // Ensure that the y-axis is not affected by zoom
        y.range([height - margin.bottom, margin.top]);
        svg.select(".y-axis").call(d3.axisLeft(y));

        svg.selectAll(".plot-point")
            .attr("cx", d => newXScale(d.x))
            .attr("cy", d => newYScale(d.y));
        svg.select(".y-axis").call(d3.axisLeft(newYScale));
    }

    function updateZoomLevel(zoomLevel) {

        document.getElementById("zoomLevel").textContent = `Graph Zoom Level: ${zoomLevel.toFixed(2)}`;
    }

    function handleMouseOver(event, d) {
        let tooltip_msg = ""
            if(d.hasOwnProperty("error_rectify_msg")){
                tooltip_msg = `Iteration Number: ${d.x}<br> Value: ${d.y} <br> ${d.error_rectify_msg}`
            }
            else{
                tooltip_msg = `Iteration Number: ${d.x}<br> Value: ${d.y}`
            }
        tooltip.transition()
            .duration(200)
            .style("opacity", .9);
        tooltip
            .html(tooltip_msg)
            .style("top", (event.pageY - 100) + "px")
            .style("left", (event.pageX - 100) + "px");

    }

    function handleMouseOut() {

        tooltip.transition()
            .duration(500)
            .style("opacity", 0);
    }
    return { "svg": svg, "x": x, "y": y, "zoom": zoom, "line": line, "width": width, "height": height }
}
let svg_objects = {}
function build_graph() {
    resetGraph();
    analytics_parameters.forEach(analytics_element => {
        let svg_node = svg_node_builder(summary_json, analytics_element)
        let div_element = document.createElement("div");
        div_element.setAttribute("id", analytics_element)
        let heading = document.createElement("p")
        heading.textContent = analytics_element.toUpperCase()
        div_element.classList.add("graph_styling")
        div_element.appendChild(svg_node.svg.node())
        document.getElementById("container").appendChild(div_element);
        svg_objects[analytics_element] = svg_node
        div_element.appendChild(heading)
    });
}
build_graph()
function zoom_refactor() {
    let svg_array = Object.values(svg_objects)
    svg_array.forEach((svg_obj) => {
        let zoom = svg_obj["zoom"]
        zoom.scaleExtent([1, Number(document.getElementById("zoom-refactor-edit").textContent)])
    })
}
document.addEventListener("DOMContentLoaded", function () {
    var editIcon = document.getElementById("zoom-edit-button");
    editIcon.addEventListener("click", function (event) {
        var inputDialog = document.createElement("div");
        inputDialog.innerHTML = '<input type="number" id="zoom-refactor-input" value="' + document.getElementById("zoom-refactor-edit").textContent + '"> <button id="save-btn" class="btn btn-primary sm">Save</button>';
        inputDialog.style.position = "absolute";
        inputDialog.style.left = (event.clientX + 10) + "px";
        inputDialog.style.top = (event.clientY + 10) + "px";
        inputDialog.style.background = "#fff";
        inputDialog.style.padding = "10px";
        inputDialog.style.border = "1px solid #ccc";
        inputDialog.style.boxShadow = "0 2px 4px rgba(0,0,0,0.1)";
        document.body.appendChild(inputDialog);

        var saveBtn = document.getElementById("save-btn");
        saveBtn.addEventListener("click", function () {
            var newValue = document.getElementById("zoom-refactor-input").value;
            document.getElementById("zoom-refactor-edit").textContent = newValue;
            zoom_refactor();
            inputDialog.remove();
        });

        // Close the dialog when clicking outside
        document.addEventListener("click", function (event) {
            if (!inputDialog.contains(event.target) && event.target !== editIcon) {
                inputDialog.remove();
            }
        });
    });
});
function capture_display_graph(analytics) {
    if (document.getElementById("DisplayAll").checked) {
        document.getElementById("DisplayAll").checked = false;
        var Checkboxes = document.querySelectorAll('input[type="checkbox"]');
        Checkboxes.forEach((checkbox) => {
            let element_unset = document.getElementById($(checkbox).attr("id"))
            if ($(checkbox).attr("id") != analytics && $(checkbox).attr("id") != "DisplayAll") {
                element_unset.checked = false
                document.getElementById(element_unset.value).setAttribute("hidden", true)

            }
        });
    }
    else {
        let current_element = document.getElementById(analytics)
        if (!current_element.checked) {
            document.getElementById(current_element.value).setAttribute("hidden", true)
        }
        else {
            document.getElementById(current_element.value).removeAttribute("hidden")
        }
    }

}
(function ($) {
    var CheckboxDropdown = function (el) {
        var _this = this;
        this.isOpen = false;
        this.areAllChecked = false;
        this.$el = $(el);
        this.$label = this.$el.find('.dropdown-label');
        this.$checkAll = this.$el.find('[data-toggle="check-all"]').first();
        this.$inputs = this.$el.find('[type="checkbox"]');

        this.onCheckBox();

        this.$label.on('click', function (e) {
            e.preventDefault();
            _this.toggleOpen();
        });

        this.$checkAll.on('click', function (e) {
            e.preventDefault();
            _this.onCheckAll();
        });

        this.$inputs.on('change', function (e) {
            _this.onCheckBox();
        });
    };

    CheckboxDropdown.prototype.onCheckBox = function () {
        this.updateStatus();
    };

    CheckboxDropdown.prototype.updateStatus = function () {
        var checked = this.$el.find(':checked');

        this.areAllChecked = false;
        this.$checkAll.html('Check All');

        if (checked.length <= 0) {
            this.$label.html('Select analytics to Display');
        }
        else if (checked.length === 1) {
            this.$label.html(checked.parent('label').text());
        }
        else if (checked.length === this.$inputs.length) {
            this.$label.html('All Selected');
            this.areAllChecked = true;
            this.$checkAll.html('Uncheck All');
        }
        else {
            this.$label.html(checked.length + ' Selected');
        }
    };

    CheckboxDropdown.prototype.onCheckAll = function (checkAll) {
        if (!this.areAllChecked || checkAll) {
            this.areAllChecked = true;
            this.$checkAll.html('Uncheck All');
            this.$inputs.prop('checked', true);
            console.log("all checked")
            var selectedCheckboxes = $('input[type=checkbox]:not checked');
            selectedCheckboxes.each(function (index, checkbox) {
                console.log($(checkbox).attr("id"));
            });
        }
        else {
            this.areAllChecked = false;
            this.$checkAll.html('Check All');
            this.$inputs.prop('checked', false);
            console.log("unchecked")
            console.log(this.$inputs)
            this.$inputs.forEach((data) => console.log(data))
        }

        this.updateStatus();
    };

    CheckboxDropdown.prototype.toggleOpen = function (forceOpen) {
        var _this = this;

        if (!this.isOpen || forceOpen) {
            this.isOpen = true;
            this.$el.addClass('on');
            $(document).on('click', function (e) {
                if (!$(e.target).closest('[data-control]').length) {
                    _this.toggleOpen();
                }
            });
        }
        else {
            this.isOpen = false;
            this.$el.removeClass('on');
            $(document).off('click');
        }
    };

    var checkboxesDropdowns = document.querySelectorAll('[data-control="checkbox-dropdown"]');
    for (var i = 0, length = checkboxesDropdowns.length; i < length; i++) {
        new CheckboxDropdown(checkboxesDropdowns[i]);
    }
})(jQuery);
$(document).ready(function () {
    $('input[id=DisplayAll]').prop('checked', true);
});
function removeAllGraphs() {
    var chk_box = document.getElementById("DisplayAll")
    if (!chk_box.checked) {
        var selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]:not(:checked)');
        selectedCheckboxes.forEach((checkbox) => {
            let element_unset = document.getElementById($(checkbox).attr("id"))
            if (element_unset.id != "DisplayAll") {
                let graph = document.getElementById(element_unset.value)
                graph.setAttribute("hidden", true)
            }
        });
    }
    else if (chk_box.checked) {
        var selectedCheckboxes = document.querySelectorAll('input[type="checkbox"]');
        selectedCheckboxes.forEach((checkbox) => {
            let element_unset = document.getElementById($(checkbox).attr("id"))
            if (element_unset.id != "DisplayAll") {
                let graph = document.getElementById(element_unset.value)
                graph.removeAttribute("hidden")
                element_unset.checked = false
            }
        });
    }
}