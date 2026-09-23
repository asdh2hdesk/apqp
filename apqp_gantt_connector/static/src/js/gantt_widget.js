/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, xml } from "@odoo/owl";
import { GanttChartAction } from "@custom_gantt/js/gantt_view";

export class GanttChartWidget extends Component {
    static template = xml`
        <div class="o_gantt_widget_container" style="height: 700px; display: flex; flex-direction: column;">
            <GanttChartAction t-if="projectId" projectId="projectId" projectName="projectName"/>
            <div t-else="" class="p-5 text-center text-muted">
                <i class="fa fa-info-circle fa-2x mb-2"/>
                <p>Please click "Sync/Add Gantt" to generate the Gantt chart for this project.</p>
            </div>
        </div>
    `;
    static components = { GanttChartAction };
    static props = { ...standardFieldProps };

    get projectId() {
        return this.props.record.data.gantt_project_id ? this.props.record.data.gantt_project_id[0] : null;
    }

    get projectName() {
        return this.props.record.data.project_name || "";
    }
}

registry.category("fields").add("apqp_gantt_widget", {
    component: GanttChartWidget,
});
