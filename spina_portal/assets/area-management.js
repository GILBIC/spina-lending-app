import {
  badge,
  detailItem,
  errorCard,
  escapeHtml,
  hasPermission,
  loadingPanel,
  settledRequest,
} from './ui.js';

function cloneAreaNode(node) {
  return {
    ...node,
    children: (node.children || []).map(cloneAreaNode),
  };
}

export function buildAreaTree(nodes = []) {
  const ordered = Array.isArray(nodes) ? nodes : [];
  const byId = new Map();

  for (const node of ordered) {
    byId.set(node.area_id, { ...node, children: [] });
  }

  const roots = [];
  for (const node of ordered) {
    const copy = byId.get(node.area_id);
    const parent = node.parent_area_id ? byId.get(node.parent_area_id) : null;
    if (parent) {
      parent.children.push(copy);
    } else {
      roots.push(copy);
    }
  }

  return roots;
}

export function areaKindLabel(node, parent = null) {
  if (node?.is_legacy_unmapped) return 'Legacy unmapped area';
  const depth = Number(node?.depth ?? (parent ? 1 : 0));
  if (depth === 0) return 'City/Municipality';
  if (depth === 1) return 'Barangay';
  return 'Subarea';
}

function collectorMatches(collector, query) {
  if (!collector) return false;
  return [collector.full_name, collector.username]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(query));
}

function nodeMatches(node, query) {
  return [node?.name, node?.full_path]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(query))
    || collectorMatches(node?.effective_collector, query)
    || collectorMatches(node?.explicit_collector, query);
}

export function filterAreaTree(tree = [], query = '') {
  const normalized = String(query ?? '').trim().toLowerCase();
  const roots = Array.isArray(tree) ? tree : [];
  if (!normalized) return roots.map(cloneAreaNode);

  function filterNode(node) {
    if (nodeMatches(node, normalized)) return cloneAreaNode(node);
    const children = (node.children || []).map(filterNode).filter(Boolean);
    return children.length ? { ...node, children } : null;
  }

  return roots.map(filterNode).filter(Boolean);
}

function findArea(tree, areaId) {
  for (const node of tree) {
    if (node.area_id === areaId) return node;
    const nested = findArea(node.children || [], areaId);
    if (nested) return nested;
  }
  return null;
}

function siblingAreas(tree, area) {
  if (!area) return [];
  if (!area.parent_area_id) return tree;
  return findArea(tree, area.parent_area_id)?.children || [];
}

function flattenAreaTree(tree = []) {
  const flattened = [];
  for (const node of tree) {
    flattened.push(node);
    flattened.push(...flattenAreaTree(node.children || []));
  }
  return flattened;
}

function descendantAreaIds(area) {
  const ids = new Set();
  const visit = (node) => {
    for (const child of node?.children || []) {
      ids.add(child.area_id);
      visit(child);
    }
  };
  visit(area);
  return ids;
}

function validMoveParents(tree, selected) {
  if (!selected) return [];
  const blocked = descendantAreaIds(selected);
  blocked.add(selected.area_id);
  if (selected.parent_area_id) blocked.add(selected.parent_area_id);
  return flattenAreaTree(tree).filter(
    (area) => area.is_active && !blocked.has(area.area_id),
  );
}

function renderOrderControls(node, siblings, index, canManageOrder) {
  if (!canManageOrder || siblings.length < 2) return '';
  const areaId = escapeHtml(node.area_id);
  const parentAreaId = escapeHtml(node.parent_area_id || '');
  const name = escapeHtml(node.name);
  return `<div class="area-tree-order-actions" data-area-parent-id="${parentAreaId}">
    <button class="button button-outline button-small" type="button" aria-label="Move ${name} up" data-area-order="up" data-area-id="${areaId}"${index === 0 ? ' disabled' : ''}>↑</button>
    <button class="button button-outline button-small" type="button" aria-label="Move ${name} down" data-area-order="down" data-area-id="${areaId}"${index === siblings.length - 1 ? ' disabled' : ''}>↓</button>
  </div>`;
}

function renderTreeRows(
  nodes,
  expandedAreaIds,
  selectedAreaId,
  parent = null,
  canManageOrder = false,
) {
  const siblings = nodes || [];
  return siblings.map((node, index) => {
    const hasChildren = (node.children || []).length > 0;
    const expanded = hasChildren && expandedAreaIds.has(node.area_id);
    const selected = node.area_id === selectedAreaId;
    const collector = node.effective_collector?.full_name || node.effective_collector?.username || '';
    const draggable = canManageOrder && siblings.length > 1;
    return `<div class="area-tree-branch">
      <button class="area-tree-row${selected ? ' selected' : ''}" type="button" data-area-id="${escapeHtml(node.area_id)}" data-area-parent-id="${escapeHtml(node.parent_area_id || '')}"${draggable ? ' draggable="true"' : ''}>
        <span class="area-tree-toggle" aria-hidden="true">${hasChildren ? (expanded ? '▾' : '▸') : '•'}</span>
        <span><strong>${escapeHtml(node.name)}</strong><small>${escapeHtml(areaKindLabel(node, parent))}</small></span>
        ${collector ? `<span class="meta">${escapeHtml(collector)}</span>` : ''}
      </button>
      ${renderOrderControls(node, siblings, index, canManageOrder)}
      ${expanded ? `<div class="area-tree-children">${renderTreeRows(node.children, expandedAreaIds, selectedAreaId, node, canManageOrder)}</div>` : ''}
    </div>`;
  }).join('');
}

function selectedAreaDetails(tree, selected) {
  if (!selected) return '<p>No Area selected.</p>';

  const selectedCollector = selected.effective_collector?.full_name
    || selected.effective_collector?.username
    || 'Unassigned';
  const explicitCollector = selected.explicit_collector?.full_name
    || selected.explicit_collector?.username
    || 'None';
  const sourceArea = selected.effective_collector_source_area_id
    ? findArea(tree, selected.effective_collector_source_area_id)
    : null;
  const inheritedFrom = sourceArea && sourceArea.area_id !== selected.area_id
    ? sourceArea.name
    : null;
  let ownershipSummary = '<p><strong>Unassigned</strong></p>';
  if (selected.explicit_collector) {
    ownershipSummary = `<p><strong>Explicit:</strong> ${escapeHtml(explicitCollector)}</p>`;
  } else if (selected.effective_collector && inheritedFrom) {
    ownershipSummary = `<p><strong>Inherited:</strong> ${escapeHtml(selectedCollector)} from ${escapeHtml(inheritedFrom)}</p>`;
  } else if (selected.effective_collector) {
    ownershipSummary = `<p><strong>Inherited:</strong> ${escapeHtml(selectedCollector)}</p>`;
  }

  return `<div class="section-heading area-details-heading">
      <div><p class="eyebrow">${escapeHtml(areaKindLabel(selected))}</p><h3>${escapeHtml(selected.name)}</h3></div>
      ${badge(selected.is_active ? 'active' : 'inactive')}
    </div>
    <p class="area-path">${escapeHtml(selected.full_path)}</p>
    <div class="area-collector-summary">
      ${ownershipSummary}
      <p><strong>Effective Collector:</strong> ${escapeHtml(selectedCollector)}</p>
      <p><strong>Explicit Collector:</strong> ${escapeHtml(explicitCollector)}</p>
      ${inheritedFrom ? `<p><strong>Inherited from:</strong> ${escapeHtml(inheritedFrom)}</p>` : ''}
    </div>
    <div class="detail-grid area-counts">
      ${detailItem('Direct Clients:', escapeHtml(selected.direct_client_count ?? 0))}
      ${detailItem('Subtree Clients:', escapeHtml(selected.subtree_client_count ?? 0))}
      ${detailItem('Child Areas:', escapeHtml(selected.child_count ?? 0))}
    </div>`;
}

function childCreateLabel(selected) {
  if (!selected || selected.is_legacy_unmapped) return null;
  return Number(selected.depth ?? 0) === 0 ? '+ Add Barangay' : '+ Add Subarea';
}

function rootCreateControl(session) {
  if (!hasPermission(session, 'area.manage')) return '';
  return '<button class="button button-outline button-small" type="button" data-area-action="add-root">+ Add City/Municipality</button>';
}

function actionControls(selected, session) {
  if (!selected) return '';
  const actions = [];
  if (hasPermission(session, 'area.manage')) {
    const createLabel = childCreateLabel(selected);
    if (createLabel) {
      actions.push(`<button class="button button-outline button-small" type="button" data-area-action="add-child">${escapeHtml(createLabel)}</button>`);
    }
    actions.push('<button class="button button-outline button-small" type="button" data-area-action="rename">Rename</button>');
    if (selected.is_active) {
      actions.push('<button class="button button-outline button-small" type="button" data-area-action="move">Move</button>');
    }
  }
  if (hasPermission(session, 'area.collector.assign')) {
    actions.push('<button class="button button-outline button-small" type="button" data-area-action="collector">Collector</button>');
  }
  if (hasPermission(session, 'area.client.assign')) {
    actions.push('<button class="button button-outline button-small" type="button" data-area-action="client-transfer">Move Client</button>');
  }
  if (hasPermission(session, 'area.retire')) {
    actions.push(`<button class="button button-outline button-small" type="button" data-area-action="${selected.is_active ? 'retire' : 'reactivate'}">${selected.is_active ? 'Retire' : 'Reactivate'}</button>`);
  }
  if (!actions.length) return '';
  return `<div class="action-row area-actions">${actions.join('')}</div>`;
}

function editorMarkup(editor, selected) {
  if (!editor) return '';
  const isRename = editor.kind === 'rename';
  const heading = isRename ? 'Rename Area' : editor.label || 'Add Area';
  const initialName = isRename ? selected?.name || '' : '';
  return `<form class="entry-form area-editor" data-area-editor="${escapeHtml(editor.kind)}">
    <div class="section-heading"><div><h3>${escapeHtml(heading)}</h3><p>SPINA recalculates the authoritative path on the server.</p></div></div>
    <label>Area name<input name="name" value="${escapeHtml(initialName)}" maxlength="160" autocomplete="off"></label>
    <div class="action-row">
      <button class="button button-primary button-small" type="submit">${isRename ? 'Save name' : 'Create Area'}</button>
    </div>
  </form>`;
}

function collectorEditorMarkup(collectorEditor, selected, collectors = []) {
  if (!collectorEditor || !selected) return '';
  const selectedCollectorId = collectorEditor.selectedCollectorUserId || '';
  const selectedCollector = collectors.find((collector) => collector.user_id === selectedCollectorId) || null;
  const selectedCollectorName = selectedCollector?.full_name || selectedCollector?.username || '';
  const options = collectors.map((collector) => {
    const collectorId = String(collector.user_id || '');
    const collectorName = collector.full_name || collector.username || collectorId;
    const selectedAttribute = collectorId === selectedCollectorId ? ' selected' : '';
    return `<option value="${escapeHtml(collectorId)}"${selectedAttribute}>${escapeHtml(collectorName)}</option>`;
  }).join('');
  const explanation = selectedCollectorName
    ? `<p class="meta">${escapeHtml(selectedCollectorName)} will handle ${escapeHtml(selected.name)} and its descendants unless a deeper Subarea has its own Collector override.</p>`
    : '';
  const removeControl = selected.explicit_collector
    ? '<button class="button button-outline button-small" type="button" data-area-collector-remove>Remove exact override</button>'
    : '';

  return `<form class="entry-form area-collector-editor" data-area-collector-editor>
    <div class="section-heading"><div><h3>Collector assignment</h3><p>SPINA keeps parent inheritance and deeper overrides authoritative on the server.</p></div></div>
    <label>Collector<select name="collector_user_id" data-area-collector-select>
      <option value="">Select Collector</option>
      ${options}
    </select></label>
    ${explanation}
    <div class="action-row">
      <button class="button button-primary button-small" type="submit">Save Collector</button>
      ${removeControl}
    </div>
  </form>`;
}

function collectorDisplayName(collector) {
  if (!collector) return 'Unassigned';
  if (typeof collector === 'string') return collector;
  return collector.full_name || collector.username || collector.user_id || 'Unassigned';
}

function formatAreaDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ''));
  if (!match) return String(value || '');
  const months = [
    'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
  ];
  const month = months[Number(match[2]) - 1] || match[2];
  return `${month} ${Number(match[3])}, ${match[1]}`;
}

function clientTransferTimingMarkup(preview) {
  if (!preview) return '';
  if (preview.timing === 'immediate') {
    return '<p>Effective: Immediately — no official collection has been recorded today.</p>';
  }
  if (preview.timing === 'next_collection_day') {
    return `<p>Effective: ${escapeHtml(formatAreaDate(preview.effective_date))} — next scheduled collection day because today already has an official collection.</p>`;
  }
  return `<p>Effective: ${escapeHtml(formatAreaDate(preview.effective_date))}</p>`;
}

function clientTransferEditorMarkup(clientTransferEditor, tree = []) {
  if (!clientTransferEditor) return '';
  const results = Array.isArray(clientTransferEditor.results) ? clientTransferEditor.results : [];
  const selectedClient = clientTransferEditor.selectedClient || null;
  const preview = clientTransferEditor.preview || null;
  const result = clientTransferEditor.result || null;
  const targetAreaId = clientTransferEditor.targetAreaId || '';
  const targetAreas = flattenAreaTree(tree).filter(
    (area) => area.is_active && area.area_id !== selectedClient?.area_id,
  );
  const targetOptions = targetAreas.map((area) => {
    const selectedAttribute = area.area_id === targetAreaId ? ' selected' : '';
    return `<option value="${escapeHtml(area.area_id)}"${selectedAttribute}>${escapeHtml(area.full_path || area.name)}</option>`;
  }).join('');
  const resultRows = results.map((client) => {
    const collector = collectorDisplayName(client.effective_collector);
    return `<button class="button button-outline area-client-result" type="button" data-area-client-id="${escapeHtml(client.client_id)}">
      <strong>${escapeHtml(client.full_name || client.client_code || client.client_id)}</strong>
      <span>${escapeHtml(client.client_code || '')}</span>
      <span>Current Area: ${escapeHtml(client.area_path || 'Unassigned')}</span>
      <span>Effective Collector: ${escapeHtml(collector)}</span>
    </button>`;
  }).join('');
  const selectedMarkup = selectedClient
    ? `<div class="area-client-transfer-selection">
        <p><strong>${escapeHtml(selectedClient.full_name || selectedClient.client_code || selectedClient.client_id)}</strong></p>
        <p>Current Area: ${escapeHtml(selectedClient.area_path || 'Unassigned')}</p>
        <p>Effective Collector: ${escapeHtml(collectorDisplayName(selectedClient.effective_collector))}</p>
        <form class="entry-form" data-area-client-transfer-preview-form>
          <label>Target Area<select name="target_area_id">
            <option value="">Select target Area</option>
            ${targetOptions}
          </select></label>
          <div class="action-row">
            <button class="button button-outline button-small" type="submit">Preview transfer</button>
          </div>
        </form>
      </div>`
    : '';
  const previewMarkup = preview
    ? `<div class="area-client-transfer-preview">
        ${clientTransferTimingMarkup(preview)}
        <p>Current Area: ${escapeHtml(preview.old_area_path || selectedClient?.area_path || 'Unassigned')}</p>
        <p>Target Area: ${escapeHtml(preview.new_area_path || findArea(tree, preview.new_area_id)?.full_path || 'Unassigned')}</p>
        <div class="action-row">
          <button class="button button-primary button-small" type="button" data-area-client-transfer-confirm>Confirm Client transfer</button>
        </div>
      </div>`
    : '';
  const resultMarkup = result
    ? `<div class="area-client-transfer-result">
        <p><strong>${result.timing === 'next_collection_day' ? 'Scheduled' : 'Transferred'}</strong></p>
        ${result.timing === 'next_collection_day'
          ? `<p>Effective: ${escapeHtml(formatAreaDate(result.effective_date))}</p>`
          : '<p>Effective: Immediately</p>'}
        <p>Current Area: ${escapeHtml(selectedClient?.area_path || result.old_area_path || 'Unassigned')}</p>
        <p>Target Area: ${escapeHtml(result.new_area_path || findArea(tree, result.new_area_id)?.full_path || 'Unassigned')}</p>
      </div>`
    : '';
  const errorMarkup = clientTransferEditor.error
    ? `<p class="error-text">${escapeHtml(clientTransferEditor.error.message || clientTransferEditor.error)}</p>`
    : '';

  return `<section class="area-client-transfer-editor">
    <div class="section-heading"><div><h3>Move Client</h3><p>SPINA decides the safe effective timing from authoritative collection and schedule data.</p></div></div>
    <form class="entry-form" data-area-client-search-form>
      <label>Find Client<input name="q" type="search" value="${escapeHtml(clientTransferEditor.query || '')}" autocomplete="off"></label>
      <div class="action-row">
        <button class="button button-outline button-small" type="submit">Search Clients</button>
      </div>
    </form>
    ${resultRows ? `<div class="area-client-results">${resultRows}</div>` : ''}
    ${selectedMarkup}
    ${previewMarkup}
    ${resultMarkup}
    ${errorMarkup}
  </section>`;
}

function moveEditorMarkup(moveEditor, selected, tree) {
  if (!moveEditor || !selected) return '';
  const selectedParentAreaId = moveEditor.selectedParentAreaId || '';
  const options = validMoveParents(tree, selected).map((area) => {
    const selectedAttribute = area.area_id === selectedParentAreaId ? ' selected' : '';
    return `<option value="${escapeHtml(area.area_id)}"${selectedAttribute}>${escapeHtml(area.full_path || area.name)}</option>`;
  }).join('');
  const preview = moveEditor.preview || null;
  const staleCount = Number(preview?.stale_delegated_access_count || 0);
  const previewMarkup = preview
    ? `<div class="area-move-preview" data-area-move-preview>
        <p><strong>Clients affected:</strong> ${escapeHtml(preview.clients_affected ?? 0)}</p>
        <p><strong>Descendant Areas affected:</strong> ${escapeHtml(preview.descendant_areas_affected ?? 0)}</p>
        <p><strong>Collector before:</strong> ${escapeHtml(collectorDisplayName(preview.effective_collector_before))}</p>
        <p><strong>Collector after:</strong> ${escapeHtml(collectorDisplayName(preview.effective_collector_after))}</p>
        ${staleCount > 0 ? `<p class="meta">${escapeHtml(staleCount)} stale delegated access ${staleCount === 1 ? 'scope' : 'scopes'} may require Staff review.</p>` : ''}
        <div class="action-row">
          <button class="button button-primary button-small" type="button" data-area-move-confirm>Confirm move</button>
        </div>
      </div>`
    : '';

  return `<form class="entry-form area-move-editor" data-area-move-preview-form>
    <div class="section-heading"><div><h3>Move Area branch</h3><p>Preview the authoritative operational impact before confirming.</p></div></div>
    <label>New parent<select name="new_parent_area_id" data-area-move-parent-select>
      <option value="">Select new parent</option>
      ${options}
    </select></label>
    <div class="action-row">
      <button class="button button-outline button-small" type="submit">Preview move</button>
    </div>
    ${previewMarkup}
  </form>`;
}

function safeMutationError(error) {
  if (Number(error?.status) === 409) {
    return new Error('Area name already exists under this parent or conflicts with the current Area structure.');
  }
  return new Error('Area change could not be saved. Refresh and try again.');
}

function safeCollectorMutationError(error) {
  if (Number(error?.status) === 409) {
    return new Error('Conflict — SPINA requires Staff review. Prior Collector ownership was kept unchanged.');
  }
  return new Error('Collector assignment could not be saved. Refresh and try again.');
}

function safeMovePreviewError(error) {
  if (Number(error?.status) === 409) {
    return new Error('Move preview conflict — refresh Area Management and try again.');
  }
  return new Error('Move preview could not be loaded. Refresh and try again.');
}

function safeMoveMutationError(error) {
  if (Number(error?.status) === 409) {
    return new Error('Move conflict — refresh Area Management and preview the branch again.');
  }
  return new Error('Area move could not be saved. Refresh and preview again.');
}

function safeClientTransferError(error) {
  if (error?.code === 'client_transfer_next_collection_day_unavailable') {
    return new Error(
      'SPINA could not find an authoritative next scheduled collection day for this Client. Refresh the schedule before retrying the Area transfer.',
    );
  }
  if (Number(error?.status) === 409) {
    return new Error('Client Area transfer conflicts with the current authoritative state. Refresh and try again.');
  }
  return new Error('Client Area transfer could not be completed. Refresh and try again.');
}

export function renderAreaManagementShell({
  tree = [],
  selectedAreaId = null,
  expandedAreaIds = new Set(),
  query = '',
  session = {},
  collectors = [],
  collectorLoadError = null,
  editor = null,
  collectorEditor = null,
  moveEditor = null,
  clientTransferEditor = null,
  mutationError = null,
} = {}) {
  const expanded = expandedAreaIds instanceof Set ? expandedAreaIds : new Set(expandedAreaIds || []);
  const selected = findArea(tree, selectedAreaId) || tree[0] || null;
  const filteredTree = filterAreaTree(tree, query);
  const canManageOrder = hasPermission(session, 'area.manage');

  return `<section class="area-management">
    <header><p class="eyebrow">AREA MANAGEMENT</p><h2>Area Management</h2></header>
    <div class="area-management-grid">
      <section class="area-tree-panel">
        <label>Search area / Collector<input type="search" value="${escapeHtml(query)}" data-area-search></label>
        <div class="area-tree">${renderTreeRows(filteredTree, expanded, selected?.area_id || null, null, canManageOrder)}</div>
        ${canManageOrder ? `<div class="area-route-order-controls">${rootCreateControl(session)}<span class="meta">Route order follows the authoritative server order.</span></div>` : ''}
      </section>
      <section class="area-details-panel">
        ${selectedAreaDetails(tree, selected)}
        ${actionControls(selected, session)}
        ${editorMarkup(editor, selected)}
        ${collectorEditorMarkup(collectorEditor, selected, collectors)}
        ${moveEditorMarkup(moveEditor, selected, tree)}
        ${clientTransferEditorMarkup(clientTransferEditor, tree)}
        ${mutationError ? errorCard(mutationError, 'Area change could not be saved.') : ''}
        ${collectorLoadError ? errorCard(collectorLoadError, 'Collector choices are temporarily unavailable.') : ''}
      </section>
    </div>
  </section>`;
}

export async function mountAreaManagement(context) {
  const { root, api, session = {} } = context;
  root.innerHTML = loadingPanel('Loading authoritative Area structure…');

  const canManageAreas = hasPermission(session, 'area.manage');
  const canAssignCollector = hasPermission(session, 'area.collector.assign');
  const canAssignClient = hasPermission(session, 'area.client.assign');
  const areasRequest = settledRequest(api, '/api/v1/areas', {}, { areas: [] });
  const collectorsRequest = canAssignCollector
    ? settledRequest(api, '/api/v1/areas/collectors', {}, { collectors: [] })
    : Promise.resolve({ data: { collectors: [] }, error: null });
  const [areasResult, collectorsResult] = await Promise.all([areasRequest, collectorsRequest]);

  if (areasResult.error) {
    root.innerHTML = errorCard(areasResult.error, 'Area Management is temporarily unavailable.');
    return;
  }

  const nodes = Array.isArray(areasResult.data?.areas) ? areasResult.data.areas : [];
  const state = {
    tree: buildAreaTree(nodes),
    selectedAreaId: nodes[0]?.area_id || null,
    expandedAreaIds: new Set(nodes.filter((node) => !node.parent_area_id).map((node) => node.area_id)),
    query: '',
    collectors: Array.isArray(collectorsResult.data?.collectors) ? collectorsResult.data.collectors : [],
    editor: null,
    collectorEditor: null,
    moveEditor: null,
    clientTransferEditor: null,
    mutationError: null,
    draggingAreaId: null,
  };

  const render = () => {
    root.innerHTML = renderAreaManagementShell({
      tree: state.tree,
      selectedAreaId: state.selectedAreaId,
      expandedAreaIds: state.expandedAreaIds,
      query: state.query,
      session,
      collectors: state.collectors,
      collectorLoadError: collectorsResult.error,
      editor: state.editor,
      collectorEditor: state.collectorEditor,
      moveEditor: state.moveEditor,
      clientTransferEditor: state.clientTransferEditor,
      mutationError: state.mutationError,
    });
  };

  const reloadAreas = async () => {
    const previousSelectedAreaId = state.selectedAreaId;
    const data = await api.request('/api/v1/areas');
    const refreshedNodes = Array.isArray(data?.areas) ? data.areas : [];
    state.tree = buildAreaTree(refreshedNodes);
    state.selectedAreaId = findArea(state.tree, previousSelectedAreaId)
      ? previousSelectedAreaId
      : refreshedNodes[0]?.area_id || null;
  };

  const submitSiblingOrder = async (parentAreaId, orderedAreaIds) => {
    try {
      await api.request('/api/v1/areas/reorder', {
        method: 'POST',
        body: {
          parent_area_id: parentAreaId || null,
          ordered_area_ids: orderedAreaIds,
        },
      });
      await reloadAreas();
      state.mutationError = null;
      render();
    } catch (error) {
      state.mutationError = safeMutationError(error);
      render();
    }
  };

  render();

  root.addEventListener('click', async (event) => {
    const orderControl = event.target?.closest?.('[data-area-order]');
    if (orderControl) {
      if (!canManageAreas) return;
      const area = findArea(state.tree, orderControl.dataset.areaId);
      if (!area) return;
      const siblings = siblingAreas(state.tree, area);
      const index = siblings.findIndex((sibling) => sibling.area_id === area.area_id);
      const delta = orderControl.dataset.areaOrder === 'up' ? -1 : 1;
      const targetIndex = index + delta;
      if (index < 0 || targetIndex < 0 || targetIndex >= siblings.length) return;
      const orderedAreaIds = siblings.map((sibling) => sibling.area_id);
      [orderedAreaIds[index], orderedAreaIds[targetIndex]] = [
        orderedAreaIds[targetIndex],
        orderedAreaIds[index],
      ];
      await submitSiblingOrder(area.parent_area_id || null, orderedAreaIds);
      return;
    }

    const clientTransferConfirm = event.target?.closest?.('[data-area-client-transfer-confirm]');
    if (clientTransferConfirm) {
      if (!canAssignClient) return;
      const editor = state.clientTransferEditor;
      const client = editor?.selectedClient || null;
      const targetAreaId = editor?.targetAreaId || '';
      const preview = editor?.preview || null;
      if (
        !client
        || !targetAreaId
        || !preview
        || preview.client_id !== client.client_id
        || preview.old_area_id !== client.area_id
        || preview.new_area_id !== targetAreaId
      ) {
        if (editor) editor.preview = null;
        if (editor) editor.error = new Error('Client transfer preview is stale. Preview again before confirming.');
        render();
        return;
      }
      try {
        const transfer = await api.request(
          `/api/v1/clients/${encodeURIComponent(client.client_id)}/area-transfer`,
          {
            method: 'POST',
            body: { target_area_id: targetAreaId },
          },
        );
        editor.result = transfer;
        editor.preview = null;
        editor.error = null;
        state.mutationError = null;
        render();
      } catch (error) {
        editor.preview = null;
        editor.error = safeClientTransferError(error);
        render();
      }
      return;
    }

    const clientResult = event.target?.closest?.('[data-area-client-id]');
    if (clientResult) {
      if (!canAssignClient || !state.clientTransferEditor) return;
      const client = state.clientTransferEditor.results.find(
        (candidate) => candidate.client_id === clientResult.dataset.areaClientId,
      );
      if (!client) return;
      state.clientTransferEditor.selectedClient = client;
      state.clientTransferEditor.targetAreaId = '';
      state.clientTransferEditor.preview = null;
      state.clientTransferEditor.result = null;
      state.clientTransferEditor.error = null;
      render();
      return;
    }

    const moveConfirm = event.target?.closest?.('[data-area-move-confirm]');
    if (moveConfirm) {
      if (!canManageAreas) return;
      const selected = findArea(state.tree, state.selectedAreaId);
      const targetAreaId = state.moveEditor?.selectedParentAreaId || '';
      const preview = state.moveEditor?.preview || null;
      if (
        !selected
        || !targetAreaId
        || !preview
        || preview.area_id !== selected.area_id
        || preview.new_parent_area_id !== targetAreaId
      ) {
        state.moveEditor = state.moveEditor
          ? { ...state.moveEditor, preview: null }
          : null;
        state.mutationError = new Error('Move preview is stale. Preview the branch again before confirming.');
        render();
        return;
      }
      try {
        await api.request(`/api/v1/areas/${encodeURIComponent(selected.area_id)}/move`, {
          method: 'POST',
          body: { new_parent_area_id: targetAreaId },
        });
        await reloadAreas();
        state.editor = null;
        state.collectorEditor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
      } catch (error) {
        state.moveEditor = state.moveEditor
          ? { ...state.moveEditor, preview: null }
          : null;
        state.mutationError = safeMoveMutationError(error);
        render();
      }
      return;
    }

    const collectorRemove = event.target?.closest?.('[data-area-collector-remove]');
    if (collectorRemove) {
      if (!canAssignCollector) return;
      const selected = findArea(state.tree, state.selectedAreaId);
      if (!selected?.explicit_collector) return;
      try {
        await api.request(`/api/v1/areas/${encodeURIComponent(selected.area_id)}/collector`, {
          method: 'DELETE',
        });
        await reloadAreas();
        state.collectorEditor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
      } catch (error) {
        state.mutationError = safeCollectorMutationError(error);
        render();
      }
      return;
    }

    const action = event.target?.closest?.('[data-area-action]');
    if (action) {
      const selected = findArea(state.tree, state.selectedAreaId);
      const actionName = action.dataset.areaAction;

      if (actionName === 'collector') {
        if (!canAssignCollector || !selected) return;
        state.collectorEditor = {
          selectedCollectorUserId: selected.explicit_collector?.user_id
            || selected.effective_collector?.user_id
            || state.collectors[0]?.user_id
            || '',
        };
        state.editor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
        return;
      }

      if (actionName === 'client-transfer') {
        if (!canAssignClient) return;
        state.clientTransferEditor = {
          query: '',
          results: [],
          selectedClient: null,
          targetAreaId: '',
          preview: null,
          result: null,
          error: null,
        };
        state.editor = null;
        state.collectorEditor = null;
        state.moveEditor = null;
        state.mutationError = null;
        render();
        return;
      }

      if (!canManageAreas) return;

      if (actionName === 'move') {
        if (!selected?.is_active) return;
        state.moveEditor = {
          selectedParentAreaId: '',
          preview: null,
        };
        state.editor = null;
        state.collectorEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
        return;
      }

      if (actionName === 'add-root') {
        state.editor = {
          kind: 'create',
          parentAreaId: null,
          label: '+ Add City/Municipality',
        };
        state.collectorEditor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
        return;
      }

      if (actionName === 'add-child') {
        const label = childCreateLabel(selected);
        if (!selected || !label) return;
        state.editor = {
          kind: 'create',
          parentAreaId: selected.area_id,
          label,
        };
        state.collectorEditor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
        return;
      }

      if (actionName === 'rename') {
        if (!selected) return;
        state.editor = {
          kind: 'rename',
          areaId: selected.area_id,
          label: 'Rename Area',
        };
        state.collectorEditor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
        return;
      }
    }

    const row = event.target?.closest?.('[data-area-id]');
    if (!row) return;
    const areaId = row.dataset.areaId;
    const area = findArea(state.tree, areaId);
    if (!area) return;
    state.selectedAreaId = areaId;
    state.editor = null;
    state.collectorEditor = null;
    state.moveEditor = null;
    state.clientTransferEditor = null;
    state.mutationError = null;
    if ((area.children || []).length) {
      if (state.expandedAreaIds.has(areaId)) state.expandedAreaIds.delete(areaId);
      else state.expandedAreaIds.add(areaId);
    }
    render();
  });

  root.addEventListener('dragstart', (event) => {
    if (!canManageAreas) return;
    const row = event.target?.closest?.('[data-area-id]');
    if (!row) return;
    const area = findArea(state.tree, row.dataset.areaId);
    if (!area || siblingAreas(state.tree, area).length < 2) return;
    state.draggingAreaId = area.area_id;
    event.dataTransfer?.setData?.('text/plain', area.area_id);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  });

  root.addEventListener('dragover', (event) => {
    if (!canManageAreas || !state.draggingAreaId) return;
    const targetRow = event.target?.closest?.('[data-area-id]');
    if (!targetRow) return;
    const source = findArea(state.tree, state.draggingAreaId);
    const target = findArea(state.tree, targetRow.dataset.areaId);
    if (!source || !target || source.parent_area_id !== target.parent_area_id) return;
    event.preventDefault();
  });

  root.addEventListener('drop', async (event) => {
    if (!canManageAreas || !state.draggingAreaId) return;
    const targetRow = event.target?.closest?.('[data-area-id]');
    const source = findArea(state.tree, state.draggingAreaId);
    const target = targetRow ? findArea(state.tree, targetRow.dataset.areaId) : null;
    state.draggingAreaId = null;
    if (!source || !target || source.area_id === target.area_id) return;
    if (source.parent_area_id !== target.parent_area_id) return;

    event.preventDefault();
    const siblings = siblingAreas(state.tree, source);
    const orderedAreaIds = siblings.map((sibling) => sibling.area_id);
    const sourceIndex = orderedAreaIds.indexOf(source.area_id);
    const targetIndex = orderedAreaIds.indexOf(target.area_id);
    if (sourceIndex < 0 || targetIndex < 0) return;
    orderedAreaIds.splice(sourceIndex, 1);
    orderedAreaIds.splice(targetIndex, 0, source.area_id);
    await submitSiblingOrder(source.parent_area_id || null, orderedAreaIds);
  });

  root.addEventListener('submit', async (event) => {
    if (event.target?.matches?.('[data-area-client-search-form]')) {
      event.preventDefault();
      if (!canAssignClient || !state.clientTransferEditor) return;
      const query = String(event.target.elements?.q?.value || '').trim();
      if (!query) {
        state.clientTransferEditor.error = new Error('Enter a Client name or code before searching.');
        render();
        return;
      }
      try {
        const data = await api.request(`/api/v1/areas/clients?q=${encodeURIComponent(query)}`);
        state.clientTransferEditor.query = query;
        state.clientTransferEditor.results = Array.isArray(data?.clients) ? data.clients : [];
        state.clientTransferEditor.selectedClient = null;
        state.clientTransferEditor.targetAreaId = '';
        state.clientTransferEditor.preview = null;
        state.clientTransferEditor.result = null;
        state.clientTransferEditor.error = null;
        render();
      } catch {
        state.clientTransferEditor.error = new Error('Client search could not be loaded. Refresh and try again.');
        render();
      }
      return;
    }

    if (event.target?.matches?.('[data-area-client-transfer-preview-form]')) {
      event.preventDefault();
      if (!canAssignClient || !state.clientTransferEditor) return;
      const client = state.clientTransferEditor.selectedClient;
      const targetAreaId = String(event.target.elements?.target_area_id?.value || '').trim();
      const targetArea = findArea(state.tree, targetAreaId);
      if (!client || !targetAreaId || !targetArea?.is_active || targetAreaId === client.area_id) {
        state.clientTransferEditor.preview = null;
        state.clientTransferEditor.error = new Error('Select a different active target Area before previewing the Client transfer.');
        render();
        return;
      }
      state.clientTransferEditor.targetAreaId = targetAreaId;
      state.clientTransferEditor.preview = null;
      state.clientTransferEditor.result = null;
      try {
        const preview = await api.request(
          `/api/v1/clients/${encodeURIComponent(client.client_id)}/area-transfer-preview?target_area_id=${encodeURIComponent(targetAreaId)}`,
        );
        if (
          !preview
          || preview.client_id !== client.client_id
          || preview.old_area_id !== client.area_id
          || preview.new_area_id !== targetAreaId
        ) {
          throw new Error('Client Area transfer preview identity did not match the selected Client and Area.');
        }
        state.clientTransferEditor.preview = preview;
        state.clientTransferEditor.error = null;
        render();
      } catch (error) {
        state.clientTransferEditor.preview = null;
        state.clientTransferEditor.error = safeClientTransferError(error);
        render();
      }
      return;
    }

    if (event.target?.matches?.('[data-area-move-preview-form]')) {
      event.preventDefault();
      if (!canManageAreas) return;
      const selected = findArea(state.tree, state.selectedAreaId);
      const targetAreaId = String(event.target.elements?.new_parent_area_id?.value || '').trim();
      const validParentIds = new Set(validMoveParents(state.tree, selected).map((area) => area.area_id));
      if (!selected || !targetAreaId || !validParentIds.has(targetAreaId)) {
        if (state.moveEditor) state.moveEditor.preview = null;
        state.mutationError = new Error('Select an active valid parent before previewing the move.');
        render();
        return;
      }
      if (!state.moveEditor) {
        state.moveEditor = { selectedParentAreaId: targetAreaId, preview: null };
      } else {
        state.moveEditor.selectedParentAreaId = targetAreaId;
        state.moveEditor.preview = null;
      }
      try {
        const preview = await api.request(
          `/api/v1/areas/${encodeURIComponent(selected.area_id)}/move-preview?new_parent_area_id=${encodeURIComponent(targetAreaId)}`,
        );
        if (
          !preview
          || preview.area_id !== selected.area_id
          || preview.new_parent_area_id !== targetAreaId
        ) {
          throw new Error('Move preview identity did not match the selected branch.');
        }
        state.moveEditor.preview = preview;
        state.mutationError = null;
        render();
      } catch (error) {
        state.moveEditor.preview = null;
        state.mutationError = safeMovePreviewError(error);
        render();
      }
      return;
    }

    if (event.target?.matches?.('[data-area-collector-editor]')) {
      event.preventDefault();
      if (!canAssignCollector) return;
      const selected = findArea(state.tree, state.selectedAreaId);
      const collectorUserId = String(event.target.elements?.collector_user_id?.value || '').trim();
      if (!selected || !collectorUserId) {
        state.mutationError = new Error('Select a Collector before saving.');
        render();
        return;
      }
      try {
        await api.request(`/api/v1/areas/${encodeURIComponent(selected.area_id)}/collector`, {
          method: 'PUT',
          body: { collector_user_id: collectorUserId },
        });
        await reloadAreas();
        state.collectorEditor = null;
        state.moveEditor = null;
        state.clientTransferEditor = null;
        state.mutationError = null;
        render();
      } catch (error) {
        state.mutationError = safeCollectorMutationError(error);
        render();
      }
      return;
    }

    if (!event.target?.matches?.('[data-area-editor]')) return;
    event.preventDefault();

    const kind = event.target.dataset.areaEditor;
    const name = String(event.target.elements?.name?.value || '').trim();
    if (!name) {
      state.mutationError = new Error('Enter an Area name before saving.');
      render();
      return;
    }

    try {
      if (kind === 'create') {
        await api.request('/api/v1/areas', {
          method: 'POST',
          body: {
            parent_area_id: state.editor?.parentAreaId ?? null,
            name,
          },
        });
      } else if (kind === 'rename') {
        const areaId = state.editor?.areaId || state.selectedAreaId;
        if (!areaId) return;
        await api.request(`/api/v1/areas/${encodeURIComponent(areaId)}`, {
          method: 'PATCH',
          body: { name },
        });
      } else {
        return;
      }

      await reloadAreas();
      state.editor = null;
      state.moveEditor = null;
      state.clientTransferEditor = null;
      state.mutationError = null;
      render();
    } catch (error) {
      state.mutationError = safeMutationError(error);
      render();
    }
  });

  root.addEventListener('change', (event) => {
    if (event.target?.matches?.('[data-area-move-parent-select]')) {
      if (!state.moveEditor) return;
      state.moveEditor.selectedParentAreaId = event.target.value || '';
      state.moveEditor.preview = null;
      state.mutationError = null;
      render();
      return;
    }

    if (!event.target?.matches?.('[data-area-collector-select]')) return;
    if (!state.collectorEditor) return;
    state.collectorEditor.selectedCollectorUserId = event.target.value || '';
    state.mutationError = null;
    render();
  });

  root.addEventListener('input', (event) => {
    if (!event.target?.matches?.('[data-area-search]')) return;
    state.query = event.target.value || '';
    render();
  });
}
