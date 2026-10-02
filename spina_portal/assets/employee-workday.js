const array=value=>Array.isArray(value)?value:[];
export function employeeWorkDate(now=new Date()) {const value=new Date(now);return Number.isNaN(value.getTime())?null:new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Manila'}).format(value);}
export function attendanceGuidance({events,employeeId,workDate}) {
 const own=array(events).filter(record=>record.employee_id===employeeId && employeeWorkDate(record.payload?.captured_at)===workDate).sort((a,b)=>Date.parse(a.payload.captured_at)-Date.parse(b.payload.captured_at)||a.id.localeCompare(b.id));
 if(!own.length)return {label:'No attendance record today',primaryActions:['clock_in'],needsReview:false};
 let previous=null,state=null;
 for(const event of own){const p=event.payload,allowed=state===null?['clock_in']:state==='clock_in'||state==='break_end'?['break_start','clock_out']:state==='break_start'?['break_end']:[];
  if(event.status!=='accepted'||!allowed.includes(p.event_type)||p.previous_event_id!==previous?.id&&!(previous===null&&p.previous_event_id==null)||previous&&p.device_id!==previous.payload.device_id)return {label:'Attendance needs review',primaryActions:[],needsReview:true};
  state=p.event_type;previous=event;
 }
 return {label:state==='clock_out'?'Clock-out recorded':state==='break_start'?'Break started':state==='break_end'?'Break ended':'Clock-in recorded',primaryActions:state==='clock_out'?[]:state==='break_start'?['break_end']:['break_start','clock_out'],needsReview:false};
}
export function buildEmployeeWorkdaySummary({workspace,now=new Date()}) {
 const workDate=employeeWorkDate(now),employeeId=workspace?.actor?.employee_id;
 const own=key=>array(workspace?.[key]).filter(record=>employeeId&&record.employee_id===employeeId);
 const payroll=own('payroll').filter(record=>['approved','partially_paid','paid'].includes(record.status)).sort((a,b)=>String(b.payload.period_end||b.payload.week_start||'').localeCompare(String(a.payload.period_end||a.payload.week_start||''))||String(b.payload.payroll_kind||'').localeCompare(String(a.payload.payroll_kind||''))||b.version-a.version);
 const status=employeeId?'loaded':'unavailable';
 const records=own('attendance').filter(record=>employeeWorkDate(record.payload?.captured_at)===workDate);
 const guidance=attendanceGuidance({events:records,employeeId,workDate});
 const days=own('attendance_days').filter(day=>day.work_date===workDate),day=days.length===1?days[0]:null;
 const needsReview=guidance.needsReview||days.length>1||Boolean(day&&(day.status!=='accepted'||array(day.issues).length))||Boolean(records.length&&!day);
 const attendance={status,...guidance,records,dayReview:{status:employeeId?(day?'loaded':'not_loaded'):'unavailable',record:day},needsReview,primaryActions:needsReview||!employeeId?[]:guidance.primaryActions};
 if(!employeeId)attendance.label='Employee attendance is unavailable';
 return {workDate,attendance,tasks:{status,records:own('tasks')},requests:{status,records:own('requests')},payroll:{status:array(workspace?.setup_missing).length?'setup_incomplete':status,record:payroll[0]||null}};
}
