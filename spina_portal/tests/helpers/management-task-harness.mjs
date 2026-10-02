import assert from 'node:assert/strict';
import {setImmediate} from 'node:timers/promises';

const handles = new WeakMap();
const registered = new WeakSet();

// Exercise the real lazy task lifecycle. Other role mounts retain their current
// behavior; repeated Management mounts still start disposal synchronously.
export async function mountRoleTask(mount, context, group, task) {
  if (context.session?.user?.role !== 'management') return mount(context);
  if (!registered.has(context)) {
    const previous = context.registerWorkspaceHandle;
    context.registerWorkspaceHandle = handle => {
      handles.set(context, handle);
      previous?.(handle);
    };
    registered.add(context);
  }
  await mount(context);
  await activateManagementTask(context, group, task);
}

export async function activateManagementTask(context, group, task) {
  const handle = handles.get(context);
  assert.equal(typeof handle?.activate, 'function', 'Management must register its real task handle');
  const activated = await handle.activate(group, task);
  await setImmediate();
  return activated;
}

export function managementTestHandle(context) {
  return handles.get(context);
}
