import {setImmediate} from 'node:timers/promises';
import {mountEmployeeWorkspace} from '../../assets/roles/employee.js';
// Exercise permitted sections through the same mount-local handle as the shell.
export async function mountEmployeeAt(context,sections){let handle;const register=context.registerWorkspaceHandle;context.registerWorkspaceHandle=value=>{handle=value;register?.(value);};await mountEmployeeWorkspace(context);for(const id of sections){if(context.root.querySelector(`#${id}`)){handle.activate(id);await setImmediate();}}return handle;}
