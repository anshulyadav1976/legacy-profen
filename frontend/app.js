const state = {
  raw: null,
  cy: null,
  fullElements: null,
  viewElements: null,
  nodeById: new Map(),
  edgeList: [],
  fullAdj: new Map(),
  expandedNodeIds: new Set(),
  selectedNodeId: null,
  clusterInfo: null,
  clusterKey: null,
  colorByCluster: false,
  labelMode: "auto",
  labelEnabled: true,
};

const statusEl = document.getElementById("status");
const selectionEl = document.getElementById("selection");

const controls = {
  graphPath: document.getElementById("graphPath"),
  maxNodes: document.getElementById("maxNodes"),
  maxEdges: document.getElementById("maxEdges"),
  labelMode: document.getElementById("labelMode"),
  layoutType: document.getElementById("layoutType"),
  loadGraph: document.getElementById("loadGraph"),
  filterFunction: document.getElementById("filterFunction"),
  filterClass: document.getElementById("filterClass"),
  filterFile: document.getElementById("filterFile"),
  filterExternal: document.getElementById("filterExternal"),
  edgeCalls: document.getElementById("edgeCalls"),
  edgeImports: document.getElementById("edgeImports"),
  edgeInherits: document.getElementById("edgeInherits"),
  applyFilters: document.getElementById("applyFilters"),
  moduleFilter: document.getElementById("moduleFilter"),
  classFilter: document.getElementById("classFilter"),
  applySubgraph: document.getElementById("applySubgraph"),
  resetSubgraph: document.getElementById("resetSubgraph"),
  focusMode: document.getElementById("focusMode"),
  focusHops: document.getElementById("focusHops"),
  expandNeighborhood: document.getElementById("expandNeighborhood"),
  resetView: document.getElementById("resetView"),
  coreLogic: document.getElementById("coreLogic"),
  minDegree: document.getElementById("minDegree"),
  hubList: document.getElementById("hubList"),
  clusterSelect: document.getElementById("clusterSelect"),
  colorByCluster: document.getElementById("colorByCluster"),
  recomputeClusters: document.getElementById("recomputeClusters"),
  searchQuery: document.getElementById("searchQuery"),
  searchBtn: document.getElementById("searchBtn"),
  clearSearch: document.getElementById("clearSearch"),
};

const TYPE_COLORS = {
  Function: "#d33a2c",
  Class: "#0d9488",
  File: "#2d6a4f",
  External: "#6b625a",
};

const CLUSTER_COLORS = [
  "#d33a2c",
  "#0d9488",
  "#2d6a4f",
  "#f59e0b",
  "#7c3aed",
  "#2563eb",
  "#db2777",
  "#0891b2",
  "#7f5539",
  "#7c2d12",
];

function setStatus(text) {
  statusEl.textContent = text;
}

function extractGraph(raw) {
  if (!raw || typeof raw !== "object") {
    return { nodes: [], links: [] };
  }
  if (Array.isArray(raw.links)) {
    return {
      nodes: Array.isArray(raw.nodes) ? raw.nodes : [],
      links: raw.links,
    };
  }
  if (Array.isArray(raw.edges)) {
    return {
      nodes: Array.isArray(raw.nodes) ? raw.nodes : [],
      links: raw.edges,
    };
  }
  if (raw.elements) {
    return {
      nodes: Array.isArray(raw.elements.nodes) ? raw.elements.nodes : [],
      links: Array.isArray(raw.elements.edges) ? raw.elements.edges : [],
    };
  }
  return { nodes: [], links: [] };
}

function moduleGroupFromPath(pathValue) {
  if (!pathValue) return "";
  const normalized = pathValue.replace(/\\/g, "/");
  const marker = "/jwst-main/";
  const idx = normalized.toLowerCase().indexOf(marker);
  if (idx !== -1) {
    const remainder = normalized.slice(idx + marker.length);
    const parts = remainder.split("/").filter(Boolean);
    return parts[0] || "";
  }
  const parts = normalized.split("/").filter(Boolean);
  if (parts.length >= 2) {
    return parts[parts.length - 2];
  }
  return parts[0] || "";
}

function toElements(raw) {
  const { nodes, links } = extractGraph(raw);
  const degree = new Map();

  for (const node of nodes) {
    degree.set(node.id, 0);
  }
  for (const link of links) {
    degree.set(link.source, (degree.get(link.source) || 0) + 1);
    degree.set(link.target, (degree.get(link.target) || 0) + 1);
  }

  const elements = {
    nodes: nodes.map((node) => {
      const type = node.type || "File";
      const isExternal = Boolean(node.external || node.path === null);
      const label = node.qualname || node.name || node.path || node.id;
      const moduleGroup = moduleGroupFromPath(node.path || "");
      return {
        data: {
          id: node.id,
          label,
          type: isExternal ? "External" : type,
          external: isExternal,
          path: node.path || null,
          qualname: node.qualname || null,
          moduleGroup,
          degree: degree.get(node.id) || 0,
          expanded: false,
          cluster: null,
          clusterColor: null,
        },
      };
    }),
    edges: links.map((link, idx) => ({
      data: {
        id: `${link.source}-${link.target}-${idx}`,
        source: link.source,
        target: link.target,
        type: link.type || "LINK",
      },
    })),
  };

  return elements;
}

function buildMaps(elements) {
  state.nodeById = new Map();
  for (const node of elements.nodes) {
    state.nodeById.set(node.data.id, node);
  }
  state.edgeList = elements.edges;
  state.fullAdj = buildAdjacency(elements.edges);
}

function buildAdjacency(edges) {
  const adj = new Map();
  for (const edge of edges) {
    const source = edge.data.source;
    const target = edge.data.target;
    if (!adj.has(source)) adj.set(source, new Set());
    if (!adj.has(target)) adj.set(target, new Set());
    adj.get(source).add(target);
    adj.get(target).add(source);
  }
  return adj;
}

function cloneNode(node) {
  return { data: { ...node.data } };
}

function chooseLayout(nodeCount) {
  const selected = controls.layoutType.value;
  if (nodeCount > 1200 && selected === "cose") {
    return "grid";
  }
  return selected;
}

function applyFilter(elements) {
  const maxNodes = parseInt(controls.maxNodes.value, 10) || 800;
  const maxEdges = parseInt(controls.maxEdges.value, 10) || 4000;
  const allowedTypes = new Set();
  if (controls.filterFunction.checked) allowedTypes.add("Function");
  if (controls.filterClass.checked) allowedTypes.add("Class");
  if (controls.filterFile.checked) allowedTypes.add("File");
  if (controls.filterExternal.checked) allowedTypes.add("External");

  const allowedEdges = new Set();
  if (controls.edgeCalls.checked) allowedEdges.add("CALLS");
  if (controls.edgeImports.checked) allowedEdges.add("IMPORTS");
  if (controls.edgeInherits.checked) allowedEdges.add("INHERITS");

  let nodes = elements.nodes.filter((node) => allowedTypes.has(node.data.type));
  nodes = nodes
    .sort((a, b) => b.data.degree - a.data.degree)
    .slice(0, maxNodes)
    .map(cloneNode);

  const nodeIds = new Set(nodes.map((n) => n.data.id));
  let edges = elements.edges.filter(
    (edge) =>
      nodeIds.has(edge.data.source) &&
      nodeIds.has(edge.data.target) &&
      allowedEdges.has(edge.data.type)
  );

  if (edges.length > maxEdges) {
    const nodeDegree = new Map();
    for (const node of nodes) {
      nodeDegree.set(node.data.id, node.data.degree || 0);
    }
    edges = edges
      .map((edge) => ({
        edge,
        score:
          (nodeDegree.get(edge.data.source) || 0) +
          (nodeDegree.get(edge.data.target) || 0),
      }))
      .sort((a, b) => b.score - a.score)
      .slice(0, maxEdges)
      .map((entry) => entry.edge);
  }

  return { nodes, edges: edges.map((edge) => ({ data: { ...edge.data } })) };
}

function applyCoreLogic(elements) {
  if (!controls.coreLogic.checked) return elements;
  const minDegree = parseInt(controls.minDegree.value, 10) || 0;
  const nodes = elements.nodes.filter(
    (node) => node.data.type !== "File" && !node.data.external
  );
  const nodeIds = new Set(nodes.map((n) => n.data.id));
  const edges = elements.edges.filter(
    (edge) =>
      nodeIds.has(edge.data.source) &&
      nodeIds.has(edge.data.target) &&
      (edge.data.type === "CALLS" || edge.data.type === "INHERITS")
  );
  const view = recomputeDegrees({ nodes, edges });
  const filteredNodes = view.nodes.filter((node) => node.data.degree >= minDegree);
  const filteredIds = new Set(filteredNodes.map((n) => n.data.id));
  const filteredEdges = view.edges.filter(
    (edge) =>
      filteredIds.has(edge.data.source) && filteredIds.has(edge.data.target)
  );
  return { nodes: filteredNodes, edges: filteredEdges };
}

function applySubgraph(elements) {
  const moduleValue = controls.moduleFilter.value.trim().toLowerCase();
  const classValue = controls.classFilter.value.trim().toLowerCase();

  if (!moduleValue && !classValue) return elements;

  let candidates = elements.nodes;
  if (moduleValue) {
    candidates = candidates.filter((node) => {
      const group = (node.data.moduleGroup || "").toLowerCase();
      const path = (node.data.path || "").toLowerCase();
      return group.includes(moduleValue) || path.includes(moduleValue);
    });
  }

  let nodeIds = new Set(candidates.map((n) => n.data.id));
  if (classValue) {
    const classNodes = candidates.filter(
      (node) =>
        node.data.type === "Class" &&
        (node.data.qualname || node.data.label || "")
          .toLowerCase()
          .includes(classValue)
    );
    const classNames = classNodes.map(
      (node) => node.data.qualname || node.data.label || ""
    );
    nodeIds = new Set(classNodes.map((n) => n.data.id));
    for (const node of candidates) {
      if (node.data.type !== "Function") continue;
      const qualname = (node.data.qualname || "").toLowerCase();
      for (const className of classNames) {
        if (qualname.startsWith(className.toLowerCase() + ".")) {
          nodeIds.add(node.data.id);
        }
      }
    }
  }

  const expanded = new Set(nodeIds);
  for (const edge of elements.edges) {
    if (nodeIds.has(edge.data.source) || nodeIds.has(edge.data.target)) {
      expanded.add(edge.data.source);
      expanded.add(edge.data.target);
    }
  }

  const nodes = elements.nodes
    .filter((node) => expanded.has(node.data.id))
    .map(cloneNode);
  const edgeList = elements.edges
    .filter(
      (edge) =>
        expanded.has(edge.data.source) && expanded.has(edge.data.target)
    )
    .map((edge) => ({ data: { ...edge.data } }));

  return { nodes, edges: edgeList };
}

function computeClusters(elements) {
  const adj = buildAdjacency(elements.edges);
  const visited = new Set();
  const nodeToCluster = new Map();
  const clusters = [];

  for (const node of elements.nodes) {
    const nodeId = node.data.id;
    if (visited.has(nodeId)) continue;
    const queue = [nodeId];
    const clusterNodes = [];
    visited.add(nodeId);
    while (queue.length) {
      const current = queue.shift();
      clusterNodes.push(current);
      const neighbors = adj.get(current);
      if (!neighbors) continue;
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      }
    }
    const clusterId = clusters.length;
    for (const member of clusterNodes) {
      nodeToCluster.set(member, clusterId);
    }
    clusters.push({ id: clusterId, size: clusterNodes.length, nodes: clusterNodes });
  }

  clusters.sort((a, b) => b.size - a.size);
  return { nodeToCluster, clusters };
}

function updateClusterSelect(clusterInfo) {
  const select = controls.clusterSelect;
  const current = select.value;
  select.innerHTML = '<option value="">All clusters</option>';
  if (!clusterInfo) return;

  const topClusters = clusterInfo.clusters.slice(0, 30);
  for (const cluster of topClusters) {
    const option = document.createElement("option");
    option.value = String(cluster.id);
    option.textContent = `Cluster ${cluster.id} (${cluster.size})`;
    select.appendChild(option);
  }
  if (current) {
    select.value = current;
  }
}

function applyClusterSelection(elements, clusterInfo) {
  if (!clusterInfo) return elements;
  const selected = controls.clusterSelect.value;
  const selectedId = selected === "" ? null : parseInt(selected, 10);
  if (selectedId === null || Number.isNaN(selectedId)) {
    return elements;
  }

  const nodeIds = new Set();
  for (const node of elements.nodes) {
    if (clusterInfo.nodeToCluster.get(node.data.id) === selectedId) {
      nodeIds.add(node.data.id);
    }
  }
  const nodes = elements.nodes
    .filter((node) => nodeIds.has(node.data.id))
    .map(cloneNode);
  const edges = elements.edges
    .filter(
      (edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target)
    )
    .map((edge) => ({ data: { ...edge.data } }));

  return { nodes, edges };
}

function applyClusterData(elements) {
  if (!state.clusterInfo) return elements;
  const clusterInfo = state.clusterInfo;
  const colorBy = controls.colorByCluster.checked;
  state.colorByCluster = colorBy;

  const clusterColorMap = new Map();
  if (clusterInfo) {
    for (const cluster of clusterInfo.clusters) {
      const color = CLUSTER_COLORS[cluster.id % CLUSTER_COLORS.length];
      clusterColorMap.set(cluster.id, color);
    }
  }

  for (const node of elements.nodes) {
    const clusterId = clusterInfo.nodeToCluster.get(node.data.id);
    node.data.cluster = clusterId;
    node.data.clusterColor = clusterColorMap.get(clusterId) || null;
  }

  return elements;
}

function applyExpansion(elements) {
  if (!state.expandedNodeIds.size) return elements;
  const nodeIds = new Set(elements.nodes.map((n) => n.data.id));
  for (const nodeId of state.expandedNodeIds) {
    if (!nodeIds.has(nodeId)) {
      const node = state.nodeById.get(nodeId);
      if (node) {
        const clone = cloneNode(node);
        clone.data.expanded = true;
        elements.nodes.push(clone);
        nodeIds.add(nodeId);
      }
    }
  }
  const edges = state.edgeList.filter(
    (edge) => nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target)
  );
  return { nodes: elements.nodes, edges: edges.map((edge) => ({ data: { ...edge.data } })) };
}

function recomputeDegrees(elements) {
  const degree = new Map();
  for (const node of elements.nodes) {
    degree.set(node.data.id, 0);
  }
  for (const edge of elements.edges) {
    degree.set(edge.data.source, (degree.get(edge.data.source) || 0) + 1);
    degree.set(edge.data.target, (degree.get(edge.data.target) || 0) + 1);
  }
  const nodes = elements.nodes.map((node) => {
    const clone = cloneNode(node);
    clone.data.degree = degree.get(node.data.id) || 0;
    return clone;
  });
  return { nodes, edges: elements.edges.map((edge) => ({ data: { ...edge.data } })) };
}

function updateDatalists(elements) {
  const moduleOptions = document.getElementById("moduleOptions");
  const classOptions = document.getElementById("classOptions");
  const moduleSet = new Set();
  const classSet = new Set();
  for (const node of elements.nodes) {
    if (node.data.moduleGroup) moduleSet.add(node.data.moduleGroup);
    if (node.data.type === "Class" && node.data.qualname) {
      classSet.add(node.data.qualname);
    }
  }
  moduleOptions.innerHTML = "";
  classOptions.innerHTML = "";
  [...moduleSet]
    .sort()
    .forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      moduleOptions.appendChild(option);
    });
  [...classSet]
    .sort()
    .forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      classOptions.appendChild(option);
    });
}

function buildHubList(elements) {
  const hubs = [...elements.nodes]
    .sort((a, b) => b.data.degree - a.data.degree)
    .slice(0, 8);
  controls.hubList.innerHTML = "";
  for (const node of hubs) {
    const button = document.createElement("button");
    button.className = "list-item";
    button.textContent = `${node.data.label} (${node.data.degree})`;
    button.addEventListener("click", () => {
      focusOnNode(node.data.id);
    });
    controls.hubList.appendChild(button);
  }
}

function focusOnNode(nodeId) {
  if (!state.cy) return;
  const target = state.cy.getElementById(nodeId);
  if (!target || target.empty()) return;
  state.cy.animate({ center: { eles: target }, zoom: 1.3, duration: 300 });
  showSelection(target);
  if (controls.focusMode.checked) {
    applyFocus(target);
  }
}

function nodeColor(node) {
  if (state.colorByCluster && node.data("clusterColor")) {
    return node.data("clusterColor");
  }
  return TYPE_COLORS[node.data("type")] || "#999";
}

function shouldShowLabels(nodeCount) {
  const mode = controls.labelMode.value;
  state.labelMode = mode;
  if (mode === "on") return true;
  if (mode === "off") return false;
  return nodeCount <= 600;
}

function labelFor(node) {
  if (!state.labelEnabled) return "";
  return node.data("label") || "";
}

function initCy(elements) {
  if (state.cy) {
    state.cy.destroy();
  }

  state.cy = cytoscape({
    container: document.getElementById("cy"),
    elements,
    layout: {
      name: chooseLayout(elements.filter((el) => el.data && !el.data.source).length),
      animate: false,
      nodeRepulsion: 8000,
      nodeDimensionsIncludeLabels: true,
    },
    style: [
      {
        selector: "node",
        style: {
          "background-color": (node) => nodeColor(node),
          label: (node) => labelFor(node),
          "font-size": 8,
          "text-wrap": "ellipsis",
          "text-max-width": 120,
          color: "#1e1a16",
          "text-outline-color": "#fffaf3",
          "text-outline-width": 1,
          width: (node) => Math.max(10, Math.min(42, node.data("degree") / 3)),
          height: (node) => Math.max(10, Math.min(42, node.data("degree") / 3)),
          "border-width": (node) => (node.data("expanded") ? 3 : 1),
          "border-color": (node) => (node.data("expanded") ? "#111" : "#fffaf3"),
        },
      },
      {
        selector: "edge",
        style: {
          width: 1,
          "line-color": "#d9d0c2",
          "target-arrow-color": "#d9d0c2",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
        },
      },
      {
        selector: "edge[type = 'CALLS']",
        style: {
          "line-color": "#d33a2c",
          "target-arrow-color": "#d33a2c",
        },
      },
      {
        selector: "edge[type = 'IMPORTS']",
        style: {
          "line-color": "#2d6a4f",
          "target-arrow-color": "#2d6a4f",
        },
      },
      {
        selector: "edge[type = 'INHERITS']",
        style: {
          "line-color": "#0d9488",
          "target-arrow-color": "#0d9488",
        },
      },
      {
        selector: ".highlight",
        style: {
          "border-width": 4,
          "border-color": "#111",
        },
      },
      {
        selector: ".focus",
        style: {
          "border-width": 4,
          "border-color": "#111",
        },
      },
      {
        selector: ".dim",
        style: {
          opacity: 0.2,
        },
      },
    ],
  });

  state.cy.on("tap", "node", (evt) => {
    const node = evt.target;
    showSelection(node);
    if (controls.focusMode.checked) {
      applyFocus(node);
    }
  });

  state.cy.on("tap", (evt) => {
    if (evt.target === state.cy) {
      clearSelection();
    }
  });
}

function applyFocus(node) {
  if (!state.cy) return;
  const hops = parseInt(controls.focusHops.value, 10) || 1;
  const neighborhood = collectNeighborhoodFromCy(node.id(), hops);
  state.cy.elements().removeClass("focus").addClass("dim");
  neighborhood.removeClass("dim").addClass("focus");
}

function collectNeighborhoodFromCy(nodeId, hops) {
  const start = state.cy.getElementById(nodeId);
  let frontier = start;
  let visited = start;

  for (let step = 0; step < hops; step += 1) {
    const neighbors = frontier.neighborhood();
    visited = visited.union(neighbors);
    frontier = neighbors;
  }

  return visited;
}

function showSelection(node) {
  const data = node.data();
  state.selectedNodeId = data.id;
  const lines = [
    ["Label", data.label],
    ["Type", data.type],
    ["ID", data.id],
    ["Path", data.path || "-"],
    ["Qualname", data.qualname || "-"],
    ["Module", data.moduleGroup || "-"],
    ["Cluster", data.cluster ?? "-"],
    ["Degree", data.degree],
  ];
  selectionEl.innerHTML = lines
    .map(
      ([label, value]) =>
        `<div class="item"><span>${label}</span><span>${value}</span></div>`
    )
    .join("");
}

function clearSelection() {
  state.selectedNodeId = null;
  selectionEl.innerHTML = '<div class="muted">No node selected.</div>';
  if (state.cy) {
    state.cy.elements().removeClass("focus").removeClass("dim");
  }
}

function applySearch(query) {
  if (!state.cy) return;
  const trimmed = query.trim().toLowerCase();
  state.cy.elements().removeClass("highlight");

  if (!trimmed) return;

  const matches = state.cy.nodes().filter((node) => {
    const label = (node.data("label") || "").toLowerCase();
    const id = (node.data("id") || "").toLowerCase();
    return label.includes(trimmed) || id.includes(trimmed);
  });

  matches.addClass("highlight");
  if (matches.length) {
    state.cy.animate({
      center: { eles: matches },
      zoom: 1.2,
      duration: 400,
    });
  }
}

function expandNeighborhood() {
  if (!state.selectedNodeId) {
    setStatus("Select a node to expand");
    return;
  }
  const hops = parseInt(controls.focusHops.value, 10) || 1;
  const neighbors = bfs(state.fullAdj, state.selectedNodeId, hops);
  for (const nodeId of neighbors) {
    state.expandedNodeIds.add(nodeId);
  }
  renderGraph();
}

function bfs(adj, start, hops) {
  const visited = new Set([start]);
  let frontier = new Set([start]);

  for (let step = 0; step < hops; step += 1) {
    const next = new Set();
    for (const node of frontier) {
      const neighbors = adj.get(node);
      if (!neighbors) continue;
      for (const neighbor of neighbors) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          next.add(neighbor);
        }
      }
    }
    frontier = next;
  }
  return visited;
}

async function loadGraph() {
  const path = controls.graphPath.value.trim();
  if (!path) {
    setStatus("Graph path missing");
    return;
  }

  setStatus("Loading graph JSON...");
  const response = await fetch(path);
  if (!response.ok) {
    setStatus(`Failed to load (${response.status})`);
    return;
  }
  const data = await response.json();
  state.raw = data;
  const elements = toElements(data);
  state.fullElements = elements;
  buildMaps(elements);
  updateDatalists(elements);

  const { nodes, links } = extractGraph(data);
  if (!nodes.length && !links.length) {
    console.warn("Unrecognized graph JSON", data);
    setStatus("Invalid graph JSON (missing nodes/links)");
    return;
  }
  state.expandedNodeIds.clear();
  state.clusterInfo = null;
  state.clusterKey = null;
  controls.clusterSelect.value = "";
  setStatus(`Loaded ${nodes.length} nodes / ${links.length} edges`);
  renderGraph();
}

function renderGraph() {
  if (!state.fullElements) return;
  setStatus("Rendering...");
  let view = applyFilter(state.fullElements);
  view = applyCoreLogic(view);
  view = applySubgraph(view);
  view = recomputeDegrees(view);

  const viewKey = `${view.nodes.length}:${view.edges.length}`;
  if (state.clusterKey !== viewKey) {
    state.clusterKey = viewKey;
    state.clusterInfo = null;
    controls.clusterSelect.value = "";
  }

  view = applyClusterData(view);
  view = applyClusterSelection(view, state.clusterInfo);
  view = applyExpansion(view);
  view = recomputeDegrees(view);
  state.viewElements = view;
  state.labelEnabled = shouldShowLabels(view.nodes.length);

  initCy([...view.nodes, ...view.edges]);
  buildHubList(view);
  setStatus(`Showing ${view.nodes.length} nodes / ${view.edges.length} edges`);
}

controls.loadGraph.addEventListener("click", () => {
  loadGraph().catch((err) => {
    console.error(err);
    setStatus("Failed to load graph");
  });
});

controls.applyFilters.addEventListener("click", () => {
  renderGraph();
});

controls.maxNodes.addEventListener("change", () => {
  renderGraph();
});

controls.maxEdges.addEventListener("change", () => {
  renderGraph();
});

controls.labelMode.addEventListener("change", () => {
  renderGraph();
});

controls.layoutType.addEventListener("change", () => {
  renderGraph();
});

controls.applySubgraph.addEventListener("click", () => {
  renderGraph();
});

controls.resetSubgraph.addEventListener("click", () => {
  controls.moduleFilter.value = "";
  controls.classFilter.value = "";
  renderGraph();
});

controls.expandNeighborhood.addEventListener("click", () => {
  expandNeighborhood();
});

controls.resetView.addEventListener("click", () => {
  state.expandedNodeIds.clear();
  controls.clusterSelect.value = "";
  renderGraph();
});

controls.recomputeClusters.addEventListener("click", () => {
  if (!state.viewElements) return;
  setStatus("Computing clusters...");
  state.clusterInfo = computeClusters(state.viewElements);
  updateClusterSelect(state.clusterInfo);
  renderGraph();
});

controls.clusterSelect.addEventListener("change", () => {
  if (!state.clusterInfo) {
    setStatus("Compute clusters first");
    return;
  }
  renderGraph();
});

controls.colorByCluster.addEventListener("change", () => {
  if (!state.clusterInfo && controls.colorByCluster.checked) {
    setStatus("Compute clusters first");
    controls.colorByCluster.checked = false;
    return;
  }
  state.colorByCluster = controls.colorByCluster.checked;
  if (state.cy) state.cy.style().update();
});

controls.focusMode.addEventListener("change", () => {
  if (!state.cy) return;
  if (!controls.focusMode.checked) {
    state.cy.elements().removeClass("focus").removeClass("dim");
    return;
  }
  if (state.selectedNodeId) {
    const node = state.cy.getElementById(state.selectedNodeId);
    if (node) applyFocus(node);
  }
});

controls.focusHops.addEventListener("change", () => {
  if (!controls.focusMode.checked || !state.selectedNodeId) return;
  const node = state.cy.getElementById(state.selectedNodeId);
  if (node) applyFocus(node);
});

controls.coreLogic.addEventListener("change", () => {
  renderGraph();
});

controls.minDegree.addEventListener("change", () => {
  renderGraph();
});

controls.searchBtn.addEventListener("click", () => {
  applySearch(controls.searchQuery.value);
});

controls.clearSearch.addEventListener("click", () => {
  controls.searchQuery.value = "";
  applySearch("");
});

window.addEventListener("DOMContentLoaded", () => {
  clearSelection();
  setStatus("Idle");
});