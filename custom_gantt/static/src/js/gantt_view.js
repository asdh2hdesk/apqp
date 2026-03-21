/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, onPatched, useRef, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const COLORS = [
    "#875a7b","#e74c3c","#e67e22","#f1c40f","#2ecc71",
    "#3498db","#9b59b6","#34495e","#1abc9c","#e91e63",
    "#00bcd4","#8bc34a","#ff5722","#607d8b",
];

function parseDate(val) {
    if (!val) return null;
    const d = new Date(val.replace(" ", "T"));
    return isNaN(d.getTime()) ? null : d;
}
function startOfDay(d) { const r=new Date(d); r.setHours(0,0,0,0); return r; }
function addDays(d,n)   { const r=new Date(d); r.setDate(r.getDate()+n); return r; }
function diffDays(a,b)  { return Math.round((startOfDay(b)-startOfDay(a))/86400000); }
function startOfMonth(d){ return new Date(d.getFullYear(),d.getMonth(),1); }
function endOfMonth(d)  { return new Date(d.getFullYear(),d.getMonth()+1,0,23,59,59); }
function startOfWeek(d) { const r=new Date(d); r.setDate(r.getDate()-((r.getDay()+6)%7)); r.setHours(0,0,0,0); return r; }
function endOfWeek(d)   { return addDays(startOfWeek(d),6); }
function fmtMY(d)       { return d.toLocaleDateString("en-GB",{month:"short",year:"numeric"}); }
function fmtDM(d)       { return d ? d.toLocaleDateString("en-GB",{day:"2-digit",month:"short"}) : "—"; }
function sameDay(a,b)   { return a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate(); }
function isWknd(d)      { return d.getDay()===0||d.getDay()===6; }
function weekNum(d)     { const t=new Date(d); t.setHours(0,0,0,0); t.setDate(t.getDate()+3-(t.getDay()+6)%7); const w=new Date(t.getFullYear(),0,4); return 1+Math.round(((t-w)/86400000-3+(w.getDay()+6)%7)/7); }
function calcDuration(s,e){ if(!s||!e) return '—'; const d=Math.round((e-s)/86400000); return d+(d===1?' day':' days'); }
function isOverdue(stop, prog){ if(!stop) return false; return startOfDay(stop)<startOfDay(new Date())&&prog<100; }

const COL_W  = 42;
const ROW_H  = 36;
const NAME_W = 940;
const HDR_H  = 36;

function buildWBSRows(records) {
    const map = {};
    records.forEach(r => { map[r.id] = { ...r, children: [] }; });
    const roots = [];
    records.forEach(r => {
        const pid = r.parent_id && (Array.isArray(r.parent_id) ? r.parent_id[0] : r.parent_id);
        if (pid && map[pid]) map[pid].children.push(map[r.id]);
        else roots.push(map[r.id]);
    });
    const result = [];
    let rc = 0;
    function walk(node, level, ps) {
        node._serial = ps ? ps+'.'+node._childIdx : String(++rc);
        node._level  = level;
        result.push(node);
        let ci=0; node.children.forEach(c => { c._childIdx=++ci; walk(c,level+1,node._serial); });
    }
    let ci=0; roots.forEach(r => { r._childIdx=++ci; walk(r,0,''); ci=rc; });
    return result;
}

class GanttChartAction extends Component {
    static template = xml`
<div class="o_action d-flex flex-column" style="height:100%;overflow:hidden;background:#fff;font-family:inherit;">

  <!-- TOOLBAR -->
  <div style="display:flex;align-items:center;gap:8px;padding:8px 14px;background:#1a2744;flex-shrink:0;flex-wrap:wrap;">
    <i class="fa fa-tasks" style="color:#1abc9c;font-size:17px;"/>
    <span style="font-weight:700;font-size:15px;color:#fff;" t-esc="title"/>
    <div class="btn-group ms-3">
      <button class="btn btn-sm" style="background:#2a4080;color:#fff;border:1px solid #3d5aad;" t-on-click="()=>this.navigate(-1)"><i class="fa fa-chevron-left"/></button>
      <button class="btn btn-sm" style="background:#2a4080;color:#fff;border:1px solid #3d5aad;" t-on-click="goToday">Today</button>
      <button class="btn btn-sm" style="background:#2a4080;color:#fff;border:1px solid #3d5aad;" t-on-click="()=>this.navigate(1)"><i class="fa fa-chevron-right"/></button>
    </div>
    <div class="btn-group ms-2">
      <button class="btn btn-sm" style="background:#2a4080;color:#fff;border:1px solid #3d5aad;" t-on-click="scrollLeft"><i class="fa fa-angle-double-left"/> Scroll</button>
      <button class="btn btn-sm" style="background:#2a4080;color:#fff;border:1px solid #3d5aad;" t-on-click="scrollRight">Scroll <i class="fa fa-angle-double-right"/></button>
    </div>
    <div class="btn-group ms-auto">
      <button t-attf-class="btn btn-sm {{ state.scale==='week'  ? 'btn-warning':'btn-outline-light' }}" style="color:#fff;" t-on-click="()=>this.setScale('week')">Week</button>
      <button t-attf-class="btn btn-sm {{ state.scale==='month' ? 'btn-warning':'btn-outline-light' }}" style="color:#fff;" t-on-click="()=>this.setScale('month')">Month</button>
      <button t-attf-class="btn btn-sm {{ state.scale==='full'  ? 'btn-warning':'btn-outline-light' }}" style="color:#fff;" t-on-click="()=>this.setScale('full')">Full</button>
    </div>
    <button class="btn btn-success btn-sm ms-2" style="color:#fff;" t-on-click="createTask"><i class="fa fa-plus me-1"/>New Task</button>
    <button class="btn btn-sm ms-1" style="background:#8e44ad;color:#fff;border:none;" t-on-click="exportGantt">
      <i class="fa fa-download me-1"/>Export
    </button>
    <button class="btn btn-sm ms-1" style="background:#e67e22;color:#fff;border:none;" t-on-click="openMOM" t-if="projectId">
      <i class="fa fa-file-text-o me-1"/>MOM
    </button>
  </div>

  <!-- LEGEND -->
  <div style="display:flex;align-items:center;gap:16px;padding:4px 14px;background:#1e3060;flex-shrink:0;font-size:11px;color:#a8bde0;">
    <span><i class="fa fa-square me-1" style="color:#2c3e50;"/> Parent Task</span>
    <span><i class="fa fa-square me-1" style="color:#3498db;"/> On Track</span>
    <span><i class="fa fa-square me-1" style="color:#e74c3c;"/> Overdue</span>
    <span><i class="fa fa-square me-1" style="color:#2ecc71;"/> Completed</span>
    <span><i class="fa fa-long-arrow-right me-1" style="color:#2c3e50;"/> Dependency</span>
  </div>

  <!-- LOADING -->
  <div t-if="state.loading" style="display:flex;justify-content:center;align-items:center;flex:1;color:#6c757d;">
    <div style="text-align:center;"><i class="fa fa-spinner fa-spin fa-2x" style="display:block;margin-bottom:10px;"/>Loading…</div>
  </div>

  <!-- MAIN BODY -->
  <div t-if="!state.loading" style="display:flex;flex:1 1 auto;min-height:0;overflow:hidden;">

    <!-- LEFT WBS PANEL -->
    <div t-att-style="'flex-shrink:0;width:'+namePanelW+'px;display:flex;flex-direction:column;border-right:2px solid #bdc3c7;background:#fff;z-index:10;'">
      <!-- Header -->
      <div style="flex-shrink:0;height:36px;background:#1e3060;display:flex;align-items:stretch;border-bottom:2px solid #0d1f4a;">
        <div style="width:36px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#a8bde0;border-right:1px solid #2a4080;">NO.</div>
        <div style="width:260px;flex-shrink:0;display:flex;align-items:center;padding:0 6px;font-size:10px;font-weight:700;color:#a8bde0;border-right:1px solid #2a4080;">TASK NAME</div>
        <div style="width:55px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#a8bde0;border-right:1px solid #2a4080;">DUR.</div>
        <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#7eb8f7;border-right:1px solid #2a4080;">PLAN START</div>
        <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#7eb8f7;border-right:1px solid #2a4080;">PLAN END</div>
        <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#4ade80;border-right:1px solid #2a4080;">ACT START</div>
        <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#4ade80;border-right:1px solid #2a4080;">ACT END</div>
        <div style="width:100px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#a8bde0;border-right:1px solid #2a4080;">ASSIGNED TO</div>
        <div style="width:110px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#a8bde0;border-right:1px solid #2a4080;">REMARK</div>
        <div style="width:55px;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#a8bde0;">%</div>
      </div>
      <!-- Rows -->
      <div t-ref="nameRows" style="overflow:hidden;flex:1;">
        <div t-ref="nameRowsWrap">
          <t t-foreach="wbsRows" t-as="row" t-key="'n_'+row.id">
            <div t-att-style="nameRowStyle(row)" t-att-data-row-idx="row_index">

              <!-- Sr. No. -->
              <div style="width:36px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;font-size:11px;font-weight:700;color:#7f8c8d;font-family:monospace;">
                <t t-esc="row._serial"/>
              </div>

              <!-- Task Name (editable) -->
              <div t-att-style="'width:260px;flex-shrink:0;display:flex;align-items:flex-start;border-right:1px solid #ecf0f1;padding:4px 4px 4px '+(4+row._level*14)+'px;'">
                <i t-if="row.children.length > 0 and state.collapsed[row.id]"  class="fa fa-caret-right me-1" style="color:#7f8c8d;cursor:pointer;flex-shrink:0;" t-on-click.stop="()=>this.toggleCollapse(row.id)"/>
                <i t-if="row.children.length > 0 and !state.collapsed[row.id]" class="fa fa-caret-down me-1"  style="color:#7f8c8d;cursor:pointer;flex-shrink:0;" t-on-click.stop="()=>this.toggleCollapse(row.id)"/>
                <i t-if="row.children.length === 0 and row._level > 0" class="fa fa-circle me-1" style="font-size:5px;color:#95a5a6;flex-shrink:0;"/>
                <i t-if="row._overdue" class="fa fa-exclamation-circle me-1" style="color:#e74c3c;flex-shrink:0;font-size:10px;"/>
                <textarea
                          t-att-style="'width:100%;border:none;background:transparent;outline:none;cursor:text;font-size:11px;resize:none;overflow:hidden;line-height:1.4;padding:0;white-space:pre-wrap;word-break:break-word;min-height:18px;'+(row.children.length>0?'font-weight:600;color:#2c3e50;':'color:#34495e;')+(row._overdue?'color:#e74c3c;':'')"
                          t-on-change="(e)=>this.saveField(row.id,'name',e.target.value)"
                          t-on-click.stop="()=>{}"
                          t-esc="row.name"/>
              </div>

              <!-- Duration (read-only) -->
              <div style="width:55px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;font-size:10px;color:#7f8c8d;white-space:nowrap;">
                <t t-esc="row._duration"/>
              </div>

              <!-- Planned Start (editable date) -->
              <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;padding:1px;">
                <input type="date"
                       t-att-value="row._planStartISO"
                       style="width:100%;border:none;background:transparent;font-size:9px;color:#2980b9;text-align:center;cursor:pointer;outline:none;"
                       t-on-change="(e)=>this.saveField(row.id,'date_start',e.target.value)"/>
              </div>

              <!-- Planned End (editable date) -->
              <div t-att-style="'width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;padding:1px;'+(row._overdue?'background:#fff5f5;':'')">
                <input type="date"
                       t-att-value="row._planEndISO"
                       style="width:100%;border:none;background:transparent;font-size:9px;color:#e74c3c;text-align:center;cursor:pointer;outline:none;"
                       t-on-change="(e)=>this.saveField(row.id,'date_stop',e.target.value)"/>
              </div>

              <!-- Actual Start (editable date) -->
              <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;padding:1px;">
                <input type="date"
                       t-att-value="row._actStartISO"
                       style="width:100%;border:none;background:transparent;font-size:9px;color:#27ae60;text-align:center;cursor:pointer;outline:none;"
                       t-on-change="(e)=>this.saveField(row.id,'actual_date_start',e.target.value)"/>
              </div>

              <!-- Actual End (editable date) -->
              <div style="width:70px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;padding:1px;">
                <input type="date"
                       t-att-value="row._actEndISO"
                       style="width:100%;border:none;background:transparent;font-size:9px;color:#27ae60;text-align:center;cursor:pointer;outline:none;"
                       t-on-change="(e)=>this.saveField(row.id,'actual_date_stop',e.target.value)"/>
              </div>

              <!-- Assigned To (editable - click to open task form for user selection) -->
              <div style="width:100px;flex-shrink:0;display:flex;align-items:center;justify-content:center;border-right:1px solid #ecf0f1;padding:1px 2px;position:relative;">
                <input type="text"
                       t-att-value="row._assignedTo"
                       placeholder="Assign..."
                       style="width:100%;border:none;background:transparent;font-size:10px;color:#34495e;text-align:center;outline:none;cursor:text;"
                       t-on-focus="(e)=>this.onAssignedFocus(row.id,e)"
                       t-on-blur="(e)=>this.onAssignedBlur(row.id,e)"
                       t-att-data-rowid="row.id"
                       t-on-input="(e)=>this.onAssignedInput(row.id,e)"
                       t-on-click.stop="()=>{}"/>
                <div t-if="state.userDropdown === row.id and state.userOptions.length"
                     style="position:absolute;top:100%;left:0;z-index:999;background:white;
                            border:1px solid #ddd;border-radius:4px;box-shadow:0 4px 12px rgba(0,0,0,.15);
                            min-width:160px;max-height:180px;overflow-y:auto;">
                  <t t-foreach="state.userOptions" t-as="u" t-key="u.id">
                    <div style="padding:6px 10px;cursor:pointer;font-size:12px;color:#2c3e50;"
                         t-esc="u.name"
                         t-on-mousedown.stop="(e)=>this.selectUser(row.id, u)"/>
                  </t>
                </div>
              </div>

              <!-- Remark (editable text) -->
              <div style="width:110px;flex-shrink:0;display:flex;align-items:center;border-right:1px solid #ecf0f1;padding:2px 4px;">
                <input type="text"
                       t-att-value="row._remark"
                       placeholder="Add remark..."
                       style="width:100%;border:none;background:transparent;font-size:10px;color:#34495e;outline:none;cursor:text;"
                       t-on-change.stop="(e)=>this.saveField(row.id,'remark',e.target.value)"
                       t-on-click.stop="()=>{}"/>
              </div>

              <!-- Progress (editable number) -->
              <div style="width:55px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:0 4px;">
                <input type="number" min="0" max="100"
                       t-att-value="row._progress"
                       style="width:100%;border:none;background:transparent;font-size:11px;font-weight:700;text-align:center;outline:none;cursor:text;"
                       t-att-style="'width:100%;border:none;background:transparent;font-size:11px;font-weight:700;text-align:center;outline:none;cursor:text;color:'+(row._overdue?'#e74c3c':row._progress===100?'#27ae60':'#2c3e50')+';'"
                       t-on-change="(e)=>this.saveField(row.id,'progress',parseFloat(e.target.value)||0)"
                       t-on-click.stop="()=>{}"/>
                <div style="width:100%;height:4px;background:#ecf0f1;border-radius:2px;margin-top:2px;">
                  <div t-att-style="'height:4px;border-radius:2px;width:'+row._progress+'%;background:'+(row._overdue?'#e74c3c':row._progress===100?'#2ecc71':'#3498db')+';'"/>
                </div>
              </div>

            </div>
          </t>
          <div t-if="wbsRows.length===0" style="height:36px;display:flex;align-items:center;padding:0 12px;color:#adb5bd;font-size:13px;">No tasks</div>
        </div>
      </div>
    </div>

    <!-- RIGHT TIMELINE -->
    <div t-ref="timelineScroll"
         style="flex:1 1 auto;overflow-x:auto;overflow-y:auto;scroll-behavior:smooth;position:relative;"
         t-on-scroll="onScroll">
      <div t-att-style="'min-width:'+timelineWidth+'px;position:relative;'">

        <!-- Day header (sticky) -->
        <div t-att-style="'display:flex;height:'+HDR_H+'px;position:sticky;top:0;z-index:8;border-bottom:2px solid #0d1a3a;'">
          <t t-foreach="dayCols" t-as="day" t-key="day.getTime()">
            <div t-att-style="dayHeaderStyle(day)">
              <div style="display:flex;flex-direction:column;align-items:center;line-height:1.2;padding:0 2px;">
                <span t-if="state.scale==='month'" style="font-size:11px;font-weight:700;" t-esc="day.toLocaleDateString('en-GB',{month:'short'})"/>
                <span t-if="state.scale==='month'" style="font-size:8px;opacity:.75;" t-esc="day.getFullYear()"/>
                <span t-if="state.scale==='week'" style="font-size:10px;font-weight:700;" t-esc="'W'+weekNum(day)"/>
                <span t-if="state.scale==='week'" style="font-size:8px;opacity:.75;" t-esc="day.toLocaleDateString('en-GB',{month:'short'})"/>
                <span t-if="state.scale!=='week' and state.scale!=='month'" style="font-size:11px;font-weight:700;" t-esc="day.getDate()"/>
                <span t-if="state.scale!=='week' and state.scale!=='month'" style="font-size:8px;opacity:.75;" t-esc="day.toLocaleDateString('en-GB',{month:'short'})"/>
              </div>
            </div>
          </t>
        </div>

        <!-- Task rows + SVG overlay in the same positioned container -->
        <div style="position:relative;" t-ref="timelineBody">

          <t t-foreach="wbsRows" t-as="row" t-key="'r_'+row.id">
            <div t-att-style="timelineRowStyle(row)" t-att-data-row-idx="row_index">
              <!-- Weekend shading -->
              <t t-foreach="dayCols" t-as="day" t-key="'bg_'+day.getTime()">
                <div t-if="isWknd(day)"
                     t-att-style="'position:absolute;top:0;left:'+Math.round((dayCols.indexOf(day)/dayCols.length)*timelineWidth)+'px;width:'+Math.round(timelineWidth/dayCols.length)+'px;height:100%;background:rgba(0,0,0,.035);pointer-events:none;'"/>
              </t>
              <!-- Today line -->
              <div t-if="todayOffset >= 0"
                   t-att-style="'position:absolute;top:0;left:'+Math.round((todayOffset/Math.max(1,totalDays))*timelineWidth)+'px;width:2px;height:100%;background:rgba(231,76,60,.7);pointer-events:none;z-index:3;'"/>
              <!-- Overdue zone -->
              <t t-if="row._visible and row._overdue and row._overdueStartPx >= 0">
                <div t-att-style="'position:absolute;top:0;left:'+row._overdueStartPx+'px;width:'+row._overdueWidthPx+'px;height:100%;background:rgba(231,76,60,.08);border-left:1px dashed #e74c3c;pointer-events:none;z-index:1;'"/>
              </t>
              <!-- Bars -->
              <t t-if="row._visible">
                <t t-if="row.children.length > 0">
                  <div t-att-style="parentBarStyle(row)" t-on-click="()=>this.openTask(row.id)">
                    <div t-attf-style="position:absolute;top:0;left:0;width:{{row._progress}}%;height:100%;background:rgba(0,0,0,0.2);pointer-events:none;border-radius:inherit;"/>
                    <span style="position:relative;z-index:1;padding:0 6px;font-size:10px;font-weight:700;color:white;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none;" t-esc="row.name"/>
                  </div>
                </t>
                <t t-else="">
                  <div t-att-style="leafBarStyle(row)" t-on-click="()=>this.openTask(row.id)">
                    <div t-attf-style="position:absolute;top:0;left:0;width:{{row._progress}}%;height:100%;background:rgba(0,0,0,0.18);pointer-events:none;border-radius:inherit;"/>
                    <span style="position:relative;z-index:1;padding:0 6px;font-size:10px;font-weight:600;color:white;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;pointer-events:none;" t-esc="row.name"/>
                    <span t-if="row._widthPx > 40" style="position:absolute;right:4px;font-size:9px;color:rgba(255,255,255,.9);pointer-events:none;" t-esc="row._progress+'%'"/>
                  </div>
                </t>
                <t t-if="row._actVisible">
                  <div t-att-style="actualBarStyle(row)">
                    <span style="position:relative;z-index:1;padding:0 5px;font-size:9px;color:rgba(255,255,255,.9);white-space:nowrap;overflow:hidden;pointer-events:none;">actual</span>
                  </div>
                </t>
              </t>
            </div>
          </t>

          <!-- SVG arrows – drawn AFTER rows so they sit on top; paths computed from real DOM -->
          <svg t-ref="arrowSvg"
               style="position:absolute;top:0;left:0;pointer-events:none;overflow:visible;z-index:1;"
               t-att-width="timelineWidth"
               t-att-height="state.svgHeight"
               xmlns="http://www.w3.org/2000/svg">
            <defs>
              <marker id="arr" markerWidth="7" markerHeight="7" refX="3.5" refY="3.5" orient="auto">
                <path d="M0,0 L0,7 L7,3.5 Z" fill="#2c3e50"/>
              </marker>
            </defs>
            <t t-foreach="state.arrows" t-as="a" t-key="a.key">
              <path t-att-d="a.path" fill="none" stroke="#2c3e50"
                    stroke-width="1.8" stroke-dasharray="5,3"
                    marker-end="url(#arr)" opacity="0.9"/>
            </t>
          </svg>

        </div><!-- /timelineBody -->

        <div t-if="wbsRows.length===0"
             style="height:120px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#adb5bd;font-size:14px;">
          <i class="fa fa-calendar-o fa-2x" style="margin-bottom:8px;opacity:.4;"/>No tasks in this period.
        </div>
      </div>
    </div>
  </div>
</div>`;

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.timelineRef  = useRef("timelineScroll");
        this.nameRowsRef  = useRef("nameRows");
        this.nameRowsWrap = useRef("nameRowsWrap");
        this.timelineBody = useRef("timelineBody");
        this.arrowSvg     = useRef("arrowSvg");

        const ctx = (this.props.action && this.props.action.context) || {};
        const savedId   = sessionStorage.getItem('gantt_project_id');
        const savedName = sessionStorage.getItem('gantt_project_name');

        if (ctx.gantt_project_id) {
            // Opened from project button — save to session
            this.projectId   = ctx.gantt_project_id;
            this.projectName = ctx.gantt_project_name || null;
            sessionStorage.setItem('gantt_project_id',   this.projectId);
            sessionStorage.setItem('gantt_project_name', this.projectName || '');
        } else if (savedId) {
            // Page refresh — restore from session
            this.projectId   = parseInt(savedId);
            this.projectName = savedName || null;
        } else {
            // No project context and no saved session — show all tasks
            this.projectId   = null;
            this.projectName = null;
        }

        this.namePanelW = NAME_W;
        this.HDR_H      = HDR_H;

        this.state = useState({
            records:[], loading:false,
            scale:"full", focus:new Date(),
            collapsed:{},
            arrows:[],
            svgHeight:0,
            userDropdown: null,
            userOptions:  [],
        });

        onWillStart(() => {
            // If no project context, redirect to Projects list
            if (!this.projectId) {
                this.action.doAction({
                    type: 'ir.actions.act_window',
                    name: 'Projects',
                    res_model: 'gantt.project',
                    view_mode: 'list,form',
                    views: [[false, 'list'], [false, 'form']],
                    target: 'current',
                });
                return;
            }
            return this._load();
        });
        onMounted(()  => setTimeout(() => { this._scrollToToday(); this._syncAndArrows(); }, 120));
        onPatched(()  => setTimeout(() => { this._syncAndArrows(); }, 30));
    }

    get title() { return this.projectName ? this.projectName+" — Gantt" : "Gantt Chart"; }

    async _load() {
        this.state.loading = true;
        try {
            const domain = this.projectId ? [["project_id","=",this.projectId]] : [];
            this.state.records = await this.orm.searchRead(
                "gantt.task", domain,
                ["id","name","date_start","date_stop","actual_date_start","actual_date_stop",
                 "color","progress","priority","parent_id","user_id","remark"],
                { limit:500, order:"id asc" }
            );
        } catch(e) { console.error("[GanttChart]", e); this.state.records = []; }
        finally    { this.state.loading = false; }
    }

    // ── Sync row heights AND recompute arrows from real DOM positions ─────
    _syncAndArrows() {
        const nameWrap = this.nameRowsWrap && this.nameRowsWrap.el;
        const timeBody = this.timelineBody && this.timelineBody.el;
        if (!nameWrap || !timeBody) return;

        // 1. Sync heights
        const nameEls = nameWrap.querySelectorAll('[data-row-idx]');
        nameEls.forEach(nr => {
            const idx = nr.dataset.rowIdx;
            const tr  = timeBody.querySelector(`[data-row-idx="${idx}"]`);
            if (!tr) return;
            nr.style.height = ''; tr.style.height = '';
            const h = Math.max(nr.offsetHeight, tr.offsetHeight, ROW_H);
            nr.style.height = h+'px'; tr.style.height = h+'px';
        });

        // 2. Build id→DOM-row map using actual offsetTop + offsetHeight
        const timeRows = timeBody.querySelectorAll('[data-row-idx]');
        const rowMap = {}; // data-row-idx → { top, height, id }
        timeRows.forEach(el => {
            rowMap[el.dataset.rowIdx] = {
                top:    el.offsetTop,
                height: el.offsetHeight,
            };
        });

        // 3. Build id→rowIndex map from wbsRows
        const rows = this.wbsRows;
        const idToIdx = {};
        rows.forEach((row, i) => { idToIdx[row.id] = i; });

        // 4. Compute total SVG height
        const totalH = timeBody.offsetHeight;

        // 5. Draw arrows using real pixel Y positions
        const arrows = [];
        rows.forEach((childRow, childIdx) => {
            if (!childRow._visible) return;
            const parentId = childRow.parent_id &&
                (Array.isArray(childRow.parent_id) ? childRow.parent_id[0] : childRow.parent_id);
            if (!parentId) return;
            const parentIdx = idToIdx[parentId];
            if (parentIdx === undefined) return;
            const parentRow = rows[parentIdx];
            if (!parentRow || !parentRow._visible) return;

            const pDom = rowMap[String(parentIdx)];
            const cDom = rowMap[String(childIdx)];
            if (!pDom || !cDom) return;

            // Start: right-centre of parent bar
            const startX = parentRow._leftPx + parentRow._widthPx;
            const startY = pDom.top + pDom.height / 2;

            // End: left-centre of child bar
            const endX = childRow._leftPx;
            const endY = cDom.top + cDom.height / 2;

            // Elbow: 12px right of parent bar end, then down, then to child
            const elbowX = startX + 10;

            const path = [
                `M ${startX} ${startY}`,
                `L ${elbowX} ${startY}`,
                `L ${elbowX} ${endY}`,
                `L ${endX}   ${endY}`,
            ].join(' ');

            arrows.push({ key:`${parentId}-${childRow.id}`, path });
        });

        this.state.arrows    = arrows;
        this.state.svgHeight = totalH;
    }

    toggleCollapse(id) {
        this.state.collapsed = { ...this.state.collapsed, [id]: !this.state.collapsed[id] };
    }

    get wbsRows() {
        const rows = buildWBSRows(this.state.records);
        const rs = startOfDay(this.rangeStart);
        const re = startOfDay(this.rangeEnd);
        const today = startOfDay(new Date());
        const collapsed = this.state.collapsed;
        const hiddenParents = new Set();
        const visible = [];
        rows.forEach(row => {
            const pid = row.parent_id && (Array.isArray(row.parent_id) ? row.parent_id[0] : row.parent_id);
            let hidden = pid && hiddenParents.has(pid);
            if (collapsed[row.id]) hiddenParents.add(row.id);
            if (pid && hiddenParents.has(pid)) { hiddenParents.add(row.id); hidden = true; }
            if (hidden) return;
            visible.push(row);
        });
        return visible.map(row => {
            const pStart = parseDate(row.date_start);
            const pStop  = parseDate(row.date_stop);
            const aStart = parseDate(row.actual_date_start);
            const aStop  = parseDate(row.actual_date_stop);
            const prog   = Math.min(100,Math.max(0,Number(row.progress)||0));
            const overdue = isOverdue(pStop, prog);
            // ISO dates for date inputs (YYYY-MM-DD)
            const toISO = (dt) => {
                if (!dt) return '';
                const d = new Date(dt.replace(' ','T'));
                return isNaN(d) ? '' : d.toISOString().slice(0,10);
            };
            row._planStartISO = toISO(row.date_start);
            row._planEndISO   = toISO(row.date_stop);
            row._actStartISO  = toISO(row.actual_date_start);
            row._actEndISO    = toISO(row.actual_date_stop);
            row._assignedTo = row.user_id ? (Array.isArray(row.user_id) ? row.user_id[1] : row.user_id) : '—';
            row._remark     = (row.remark && row.remark !== false) ? String(row.remark) : '';
            row._planStart = fmtDM(pStart); row._planEnd = fmtDM(pStop);
            row._actStart  = fmtDM(aStart); row._actEnd  = fmtDM(aStop);
            row._duration  = calcDuration(pStart, pStop);
            row._progress  = prog; row._overdue = overdue;
            if (!pStart||!pStop||startOfDay(pStop)<rs||startOfDay(pStart)>re) {
                row._visible = false;
            } else {
                row._visible = true;
                const cS = startOfDay(pStart)<rs?rs:startOfDay(pStart);
                const cE = startOfDay(pStop)>re ?re:startOfDay(pStop);
                const cw = this.colW;
                const dpC = this.state.scale==='week' ? 7 : this.state.scale==='month' ? (new Date(cS.getFullYear(),cS.getMonth()+1,0).getDate()) : 1;
                const totalPx = this.dayCols.length * cw;
                const totalD  = this.totalDays || 1;
                row._leftPx  = Math.max(0, (diffDays(rs,cS) / totalD) * totalPx);
                row._widthPx = Math.max(cw*0.4, ((diffDays(cS,cE)+1) / totalD) * totalPx);
                row._barColor = prog===100?"#2ecc71":overdue?"#e74c3c":COLORS[(Number(row.color)||0)%COLORS.length];
                if (overdue) {
                    const from=startOfDay(pStop)<rs?rs:startOfDay(pStop);
                    const to  =today>re?re:today;
                    if(from<=re&&to>=rs){
                        const totalPx2 = this.dayCols.length * this.colW;
                        const totalD2  = this.totalDays || 1;
                        row._overdueStartPx=Math.max(0,(diffDays(rs,from)/totalD2)*totalPx2);
                        row._overdueWidthPx=Math.max(this.colW,((diffDays(from,to)+1)/totalD2)*totalPx2);
                    } else { row._overdueStartPx=-1; }
                }
            }
            if(aStart&&aStop&&startOfDay(aStop)>=rs&&startOfDay(aStart)<=re){
                const as2=startOfDay(aStart)<rs?rs:startOfDay(aStart);
                const ae2=startOfDay(aStop)>re ?re:startOfDay(aStop);
                row._actVisible=true;
                const totalPx3 = this.dayCols.length * this.colW;
                const totalD3  = this.totalDays || 1;
                row._actLeftPx =Math.max(0,(diffDays(rs,as2)/totalD3)*totalPx3);
                row._actWidthPx=Math.max(this.colW*0.3,((diffDays(as2,ae2)+1)/totalD3)*totalPx3);
            } else { row._actVisible=false; }
            return row;
        });
    }

    get rangeStart() {
        if(this.state.scale==="week")  return this._fullRangeStart(); // all weeks
        if(this.state.scale==="month") return this._fullRangeStart(); // all months
        if(this.state.scale==="full")  return this._fullRangeStart();
        return startOfMonth(this.state.focus);
    }
    get rangeEnd() {
        if(this.state.scale==="week")  return this._fullRangeEnd();   // all weeks
        if(this.state.scale==="month") return this._fullRangeEnd();   // all months
        if(this.state.scale==="full")  return this._fullRangeEnd();
        return endOfMonth(this.state.focus);
    }
    get totalDays()     { return Math.max(1,diffDays(this.rangeStart,this.rangeEnd)+1); }
    get timelineWidth() { return this.dayCols.length * this.colW; }
    // All individual days (always used for bar math)
    get allDayCols() {
        const cols=[],end=startOfDay(this.rangeEnd);
        let d=startOfDay(this.rangeStart);
        while(d<=end){cols.push(new Date(d));d=addDays(d,1);}
        return cols;
    }
    // Display columns — day / week / month depending on scale
    get dayCols() {
        if (this.state.scale === 'week') {
            const weeks=[], seen=new Set();
            for (const d of this.allDayCols) {
                const ws=startOfWeek(d), key=ws.toISOString().slice(0,10);
                if(!seen.has(key)){seen.add(key);weeks.push(ws);}
            }
            return weeks;
        }
        if (this.state.scale === 'month') {
            const months=[], seen=new Set();
            for (const d of this.allDayCols) {
                const ms=startOfMonth(d), key=ms.getFullYear()+'-'+ms.getMonth();
                if(!seen.has(key)){seen.add(key);months.push(ms);}
            }
            return months;
        }
        return this.allDayCols;
    }
    // Pixel width per display column
    get colW() {
        if(this.state.scale==='week')  return 70;
        if(this.state.scale==='month') return 90;
        return 42;
    }
    get todayOffset() {
        const today=startOfDay(new Date()),rs=startOfDay(this.rangeStart);
        if(today<rs||today>startOfDay(this.rangeEnd)) return -1;
        return diffDays(rs,today);
    }
    isWknd(d){ return d.getDay()===0||d.getDay()===6; }
    weekNum(d){ const t=new Date(d); t.setHours(0,0,0,0); t.setDate(t.getDate()+3-(t.getDay()+6)%7); const w=new Date(t.getFullYear(),0,4); return 1+Math.round(((t-w)/86400000-3+(w.getDay()+6)%7)/7); }

    nameRowStyle(row) {
        const p=row.children.length>0;
        const bg=row._overdue?(p?'#fdecea':'#fff5f5'):(p?(row._level===0?'#dfe6e9':'#ecf0f1'):(row._level%2===0?'#fff':'#fafbfc'));
        return `min-height:${ROW_H}px;display:flex;align-items:stretch;border-bottom:1px solid #dfe6e9;cursor:pointer;background:${bg};`;
    }
    timelineRowStyle(row) {
        return `min-height:${ROW_H}px;height:${ROW_H}px;position:relative;border-bottom:1px solid #f0f0f0;`+
               `min-width:${this.timelineWidth}px;`+
               `background-image:repeating-linear-gradient(90deg,transparent 0,transparent ${this.colW-1}px,#ecf0f1 ${this.colW-1}px,#ecf0f1 ${this.colW}px);`;
    }
    dayHeaderStyle(day) {
        const today=sameDay(day,new Date()),wknd=isWknd(day);
        const cw = this.colW;
        return `width:${cw}px;height:${HDR_H}px;flex-shrink:0;border-right:1px solid #2a4080;box-sizing:border-box;background:#162454;`+
               `display:flex;align-items:center;justify-content:center;`+
               (today?`background:#e74c3c;color:white;font-weight:700;`:wknd?`color:#7f8c8d;`:`color:#bdc3c7;`);
    }
    parentBarStyle(row) {
        return `position:absolute;top:5px;height:26px;left:${row._leftPx}px;width:${row._widthPx}px;`+
               `background:${row._barColor||'#2c3e50'};border-radius:3px;cursor:pointer;overflow:hidden;`+
               `display:flex;align-items:center;z-index:2;box-shadow:0 2px 4px rgba(0,0,0,.25);`;
    }
    leafBarStyle(row) {
        return `position:absolute;top:8px;height:20px;left:${row._leftPx}px;width:${row._widthPx}px;`+
               `background:${row._barColor};border-radius:3px;cursor:pointer;overflow:hidden;`+
               `display:flex;align-items:center;z-index:2;box-shadow:0 1px 3px rgba(0,0,0,.2);`;
    }
    actualBarStyle(row) {
        return `position:absolute;top:28px;height:6px;left:${row._actLeftPx}px;width:${row._actWidthPx}px;`+
               `background:#27ae60;border-radius:2px;overflow:hidden;z-index:2;opacity:0.85;`;
    }

    _scrollToToday() {
        const el=this.timelineRef&&this.timelineRef.el;
        if(!el) return;
        const off=this.todayOffset;
        if(off<0) return;
        const propLeft = Math.round((off / Math.max(1, this.totalDays)) * this.timelineWidth);
        el.scrollLeft=Math.max(0, propLeft - el.clientWidth/2 + this.colW/2);
    }
    onScroll(ev) {
        const nr=this.nameRowsRef&&this.nameRowsRef.el;
        if(nr) nr.scrollTop=ev.target.scrollTop;
    }
    scrollLeft()  { const el=this.timelineRef&&this.timelineRef.el; if(el) el.scrollBy({left:-this.colW*3,behavior:"smooth"}); }
    scrollRight() { const el=this.timelineRef&&this.timelineRef.el; if(el) el.scrollBy({left: this.colW*3,behavior:"smooth"}); }

    _fullRangeStart() {
        const dates=this.state.records.map(r=>parseDate(r.date_start)).filter(Boolean);
        if(!dates.length) return startOfMonth(new Date());
        return startOfMonth(new Date(Math.min(...dates.map(d=>d.getTime()))));
    }
    _fullRangeEnd() {
        const dates=this.state.records.map(r=>parseDate(r.date_stop)).filter(Boolean);
        if(!dates.length) return endOfMonth(new Date());
        return endOfMonth(new Date(Math.max(...dates.map(d=>d.getTime()))));
    }
    navigate(dir) {
        const f=this.state.focus;
        if(this.state.scale==="week")      this.state.focus=addDays(f,dir*7);
        else if(this.state.scale==="full" || this.state.scale==="month" || this.state.scale==="week") return;
        else                               this.state.focus=new Date(f.getFullYear(),f.getMonth()+dir,1);
        setTimeout(()=>this._scrollToToday(),50);
    }
    goToday()   { this.state.focus=new Date(); setTimeout(()=>this._scrollToToday(),50); }
    setScale(s) { this.state.scale=s; setTimeout(()=>this._scrollToToday(),50); }
    async onAssignedInput(rowId, e) {
        const query = e.target.value.trim();
        if (query.length < 1) { this.state.userDropdown = null; this.state.userOptions = []; return; }
        try {
            const users = await this.orm.searchRead(
                'res.users', [['name','ilike',query]],
                ['id','name'], { limit:8 }
            );
            this.state.userOptions  = users;
            this.state.userDropdown = rowId;
        } catch(e) { console.error(e); }
    }
    onAssignedFocus(rowId, e) {
        // show dropdown if already has text
        if (e.target.value) this.onAssignedInput(rowId, { target: e.target });
    }
    onAssignedBlur(rowId, e) {
        setTimeout(() => { this.state.userDropdown = null; }, 200);
    }
    async selectUser(rowId, user) {
        this.state.userDropdown = null;
        this.state.userOptions  = [];
        await this.orm.write('gantt.task', [rowId], { user_id: user.id });
        await this._load();
    }

    async saveField(id, field, value) {
        try {
            // Convert date string to Odoo datetime format
            let writeVal = value;
            if (['date_start','date_stop','actual_date_start','actual_date_stop'].includes(field)) {
                if (!value) {
                    writeVal = false;
                } else {
                    // Odoo expects "YYYY-MM-DD HH:MM:SS"
                    writeVal = value + ' 00:00:00';
                }
            }
            if (field === 'progress') {
                writeVal = Math.min(100, Math.max(0, parseFloat(value) || 0));
            }
            await this.orm.write('gantt.task', [id], { [field]: writeVal });
            // Reload records to reflect changes
            await this._load();
        } catch(e) {
            console.error('[GanttChart] saveField error:', e);
        }
    }

    openTask(id) { this.action.doAction({type:"ir.actions.act_window",res_model:"gantt.task",res_id:id,views:[[false,"form"]],target:"current"}); }

    exportGantt() {
        if (!this.projectId) {
            alert("Please open a specific project Gantt to export.");
            return;
        }
        // Call server-side controller that generates the full Excel Gantt
        const url = `/custom_gantt/export_excel/${this.projectId}`;
        window.open(url, "_blank");
    }
    async openMOM() {
        // Call server-side method which handles access properly
        if (!this.projectId) return;
        try {
            const result = await this.orm.call(
                "gantt.project",
                "action_open_mom",
                [[this.projectId]],
                {}
            );
            this.action.doAction(result);
        } catch(e) {
            console.error("[GanttChart] openMOM error:", e);
            // Fallback: open directly
            this.action.doAction({
                type:      "ir.actions.act_window",
                name:      (this.projectName || "") + " — MOM",
                res_model: "gantt.mom",
                views:     [[false, "form"]],
                target:    "new",
                context: {
                    default_project_id: this.projectId,
                    default_subject:    "MOM — " + (this.projectName || ""),
                },
            });
        }
    }
    createTask() { this.action.doAction({type:"ir.actions.act_window",res_model:"gantt.task",views:[[false,"form"]],target:"current",context:{default_project_id:this.projectId||false}}); }
}

try {
    registry.category("actions").add("custom_gantt.GanttChartAction", GanttChartAction);
    console.log("[custom_gantt] GanttChartAction registered OK");
} catch(e) {
    console.error("[custom_gantt] Failed to register:", e);
}