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

function renderTreeRows(nodes, expandedAreaIds, selectedAreaId, parent = null) {
  return (nodes || []).map((node) => {
    const hasChildren = (node.children || []).length > 0;
    const expanded = hasChildren && expandedAreaIds.has(node.area_id);
    const selected = node.area_id === selectedAreaId;
    const collector = node.effective_collector?.full_name || node.effective_collector?.username || '';
    return `<div class="area-tree-branch">
      <button class="area-tree-row${selected ? ' selected' : ''}" type="button" data-area-id="${escapeHtml(node.area_id)}">
        <span class="area-tree-toggle" aria-hidden="true">${hasChildren ? (expanded ? '▾' : '▸') : '•'}</span>
        <span><strong>${escapeHtml(node.name)}</strong><small>${escapeHtml(areaKindLabel(node, parent))}</small></span>
        ${collector ? `<span class="meta">${escapeHtml(collector)}</span>` : ''}
      </button>
      ${expanded ? `<div class="area-tree-children">${renderTreeRows(node.children, expandedAreaIds, selectedAreaId, node)}</div>` : ''}
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

  return `<div class="section-heading area-details-heading">
      <div><p class="eyebrow">${escapeHtml(areaKindLabel(selected))}</p><h3>${escapeHtml(selected.name)}</h3></div>
      ${badge(selected.is_active ? 'active' : 'inactive')}
    </div>
    <p class="area-path">${escapeHtml(selected.full_path)}</p>
    <div class="area-collector-summary">
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

function safeMutationError(error) {
  if (Number(error?.status) === 409) {
    return new Error('Area name already exists under this parent or conflicts with the current Area structure.');
  }
  return new Error('Area change could not be saved. Refresh and try again.');
}

export function renderAreaManagementShell({
  tree = [],
  selectedAreaId = null,
  expandedAreaIds = new Set(),
  query = '',
  session = {},
  collectorLoadError = null,
  editor = null,
  mutationError = null,
} = {}) {
  const expanded = expandedAreaIds instanceof Set ? expandedAreaIds : new Set(expandedAreaIds || []);
  const selected = findArea(tree, selectedAreaId) || tree[0] || null;
  const filteredTree = filterAreaTree(tree, query);

  return `<section class="area-management">
    <header><p class="eyebrow">AREA MANAGEMENT</p><h2>Area Management</h2></header>
    <div class="area-management-grid">
      <section class="area-tree-panel">
        <label>Search area / Collector<input type="search" value="${escapeHtml(query)}" data-area-search></label>
        <div class="area-tree">${renderTreeRows(filteredTree, expanded, selected?.area_id || null)}</div>
        ${hasPermission(session, 'area.manage') ? `<div class="area-route-order-controls">${rootCreateControl(session)}<span class="meta">Route order follows the authoritative server order.</span></div>` : ''}
      </section>
      <section class="area-details-panel">
        ${selectedAreaDetails(tree, selected)}
        ${actionControls(selected, session)}
        ${editorMarkup(editor, selected)}
        ${mutationError ? errorCard(mutationError, 'Area change could not be saved.') : ''}
        ${collectorLoadError ? errorCard(collectorLoadError, 'Collector choices are temporarily unavailable.') : ''}
      </section>
    </div>
  </section>`;
}

export async function mountAreaManagement(context) {
  const { root, api, session = {} } = context;
  root.innerHTML = loadingPanel('Loading authoritative Area structure…');

  const canAssignCollector = hasPermission(session, 'area.collector.assign');
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
    mutationError: null,
  };

  const render = () => {
    root.innerHTML = renderAreaManagementShell({
      tree: state.tree,
      selectedAreaId: state.selectedAreaId,
      expandedAreaIds: state.expandedAreaIds,
      query: state.query,
      session,
      collectorLoadError: collectorsResult.error,
      editor: state.editor,
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

  render();

  root.addEventListener('click', async (event) => {
    const action = event.target?.closest?.('[data-area-action]');
    if (action) {
      if (!hasPermission(session, 'area.manage')) return;
      const selected = findArea(state.tree, state.selectedAreaId);

      if (action.dataset.areaAction === 'add-root') {
        state.editor = {
          kind: 'create',
          parentAreaId: null,
          label: '+ Add City/Municipality',
        };
        state.mutationError = null;
        render();
        return;
      }

      if (action.dataset.areaAction === 'add-child') {
        const label = childCreateLabel(selected);
        if (!selected || !label) return;
        state.editor = {
          kind: 'create',
          parentAreaId: selected.area_id,
          label,
        };
        state.mutationError = null;
        render();
        return;
      }

      if (action.dataset.areaAction === 'rename') {
        if (!selected) return;
        state.editor = {
          kind: 'rename',
          areaId: selected.area_id,
          label: 'Rename Area',
        };
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
    state.mutationError = null;
    if ((area.children || []).length) {
      if (state.expandedAreaIds.has(areaId)) state.expandedAreaIds.delete(areaId);
      else state.expandedAreaIds.add(areaId);
    }
    render();
  });

  root.addEventListener('submit', async (event) => {
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
      state.mutationError = null;
      render();
    } catch (error) {
      state.mutationError = safeMutationError(error);
      render();
    }
  });

  root.addEventListener('input', (event) => {
    if (!event.target?.matches?.('[data-area-search]')) return;
    state.query = event.target.value || '';
    render();
  });
}
