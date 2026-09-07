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

function actionControls(selected, session) {
  if (!selected) return '';
  const actions = [];
  if (hasPermission(session, 'area.manage')) {
    actions.push('<button class="button button-outline button-small" type="button" data-area-action="add-child">Add child</button>');
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

export function renderAreaManagementShell({
  tree = [],
  selectedAreaId = null,
  expandedAreaIds = new Set(),
  query = '',
  session = {},
  collectorLoadError = null,
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
        ${hasPermission(session, 'area.manage') ? '<div class="area-route-order-controls"><span class="meta">Route order follows the authoritative server order.</span></div>' : ''}
      </section>
      <section class="area-details-panel">
        ${selectedAreaDetails(tree, selected)}
        ${actionControls(selected, session)}
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
  };

  const render = () => {
    root.innerHTML = renderAreaManagementShell({
      tree: state.tree,
      selectedAreaId: state.selectedAreaId,
      expandedAreaIds: state.expandedAreaIds,
      query: state.query,
      session,
      collectorLoadError: collectorsResult.error,
    });
  };

  render();

  root.addEventListener('click', (event) => {
    const row = event.target?.closest?.('[data-area-id]');
    if (!row) return;
    const areaId = row.dataset.areaId;
    const area = findArea(state.tree, areaId);
    if (!area) return;
    state.selectedAreaId = areaId;
    if ((area.children || []).length) {
      if (state.expandedAreaIds.has(areaId)) state.expandedAreaIds.delete(areaId);
      else state.expandedAreaIds.add(areaId);
    }
    render();
  });

  root.addEventListener('input', (event) => {
    if (!event.target?.matches?.('[data-area-search]')) return;
    state.query = event.target.value || '';
    render();
  });
}
