import { escapeHtml } from './ui.js';

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
  if (!parent || Number(node?.depth ?? 0) === 0) return 'City/Municipality';
  if (Number(node?.depth ?? 0) === 1) return 'Barangay';
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

function renderTreeRows(nodes, expandedAreaIds, parent = null) {
  return (nodes || []).map((node) => {
    const hasChildren = (node.children || []).length > 0;
    const expanded = hasChildren && expandedAreaIds.has(node.area_id);
    const collector = node.effective_collector?.full_name || node.effective_collector?.username || '';
    return `<div class="area-tree-branch">
      <button class="area-tree-row" type="button" data-area-id="${escapeHtml(node.area_id)}">
        <span class="area-tree-toggle" aria-hidden="true">${hasChildren ? (expanded ? '▾' : '▸') : '•'}</span>
        <span><strong>${escapeHtml(node.name)}</strong><small>${escapeHtml(areaKindLabel(node, parent))}</small></span>
        ${collector ? `<span class="meta">${escapeHtml(collector)}</span>` : ''}
      </button>
      ${expanded ? `<div class="area-tree-children">${renderTreeRows(node.children, expandedAreaIds, node)}</div>` : ''}
    </div>`;
  }).join('');
}

export function renderAreaManagementShell({
  tree = [],
  selectedAreaId = null,
  expandedAreaIds = new Set(),
  query = '',
} = {}) {
  const expanded = expandedAreaIds instanceof Set ? expandedAreaIds : new Set(expandedAreaIds || []);
  const selected = findArea(tree, selectedAreaId) || tree[0] || null;
  const filteredTree = filterAreaTree(tree, query);
  const selectedCollector = selected?.effective_collector?.full_name || selected?.effective_collector?.username || 'Unassigned';

  return `<section class="area-management">
    <header><p class="eyebrow">AREA MANAGEMENT</p><h2>Area Management</h2></header>
    <div class="area-management-grid">
      <section class="area-tree-panel">
        <label>Search area / Collector<input type="search" value="${escapeHtml(query)}" data-area-search></label>
        <div class="area-tree">${renderTreeRows(filteredTree, expanded)}</div>
      </section>
      <section class="area-details-panel">
        ${selected ? `<p class="eyebrow">${escapeHtml(areaKindLabel(selected))}</p>
          <h3>${escapeHtml(selected.name)}</h3>
          <p>${escapeHtml(selected.full_path)}</p>
          <p><strong>Effective Collector:</strong> ${escapeHtml(selectedCollector)}</p>` : '<p>No Area selected.</p>'}
      </section>
    </div>
  </section>`;
}
