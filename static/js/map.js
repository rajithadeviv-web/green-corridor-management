/*
map.js
-------
Renders the simulated road network as an SVG graphic inside #mapContainer,
and exposes helper functions to update junction signal colors and the
emergency vehicle marker position. This is a SIMULATED map, not real GPS/geo data.
*/

const GreenCorridorMap = (() => {
  let networkData = null;
  let svgEl = null;
  let vehicleEl = null;
  let currentRoutePath = [];

  function nodeById(id) {
    return networkData.nodes.find(n => n.id === id);
  }

  async function loadNetwork() {
    const res = await fetch('/api/network');
    const data = await res.json();
    networkData = data.network;
    return networkData;
  }

  function render(containerId) {
    const container = document.getElementById(containerId);
    const ns = 'http://www.w3.org/2000/svg';
    svgEl = document.createElementNS(ns, 'svg');
    svgEl.setAttribute('viewBox', '0 0 620 480');
    svgEl.setAttribute('width', '100%');
    svgEl.setAttribute('height', '100%');
    svgEl.style.display = 'block';

    // draw edges first (so nodes sit on top)
    networkData.edges.forEach(edge => {
      const a = nodeById(edge.from);
      const b = nodeById(edge.to);
      const line = document.createElementNS(ns, 'line');
      line.setAttribute('x1', a.x); line.setAttribute('y1', a.y);
      line.setAttribute('x2', b.x); line.setAttribute('y2', b.y);
      line.setAttribute('stroke', '#1D2530');
      line.setAttribute('stroke-width', '5');
      line.setAttribute('stroke-linecap', 'round');
      line.dataset.edgeKey = edgeKey(edge.from, edge.to);
      svgEl.appendChild(line);
    });

    // draw nodes
    networkData.nodes.forEach(node => {
      const g = document.createElementNS(ns, 'g');
      g.setAttribute('id', `node-${node.id}`);

      const isTerminal = node.type === 'source' || node.type === 'destination';
      const circle = document.createElementNS(ns, 'circle');
      circle.setAttribute('cx', node.x);
      circle.setAttribute('cy', node.y);
      circle.setAttribute('r', isTerminal ? 10 : 7);
      circle.setAttribute('fill', isTerminal ? '#4CC9F0' : '#7C8798');
      circle.setAttribute('stroke', '#090C11');
      circle.setAttribute('stroke-width', '2');
      circle.setAttribute('id', `dot-${node.id}`);
      g.appendChild(circle);

      const label = document.createElementNS(ns, 'text');
      label.setAttribute('x', node.x);
      label.setAttribute('y', node.y - 14);
      label.setAttribute('text-anchor', 'middle');
      label.setAttribute('fill', '#7C8798');
      label.setAttribute('font-size', '9');
      label.setAttribute('font-family', 'JetBrains Mono, monospace');
      label.textContent = node.label;
      g.appendChild(label);

      svgEl.appendChild(g);
    });

    // vehicle marker (hidden until a trip starts)
    vehicleEl = document.createElementNS(ns, 'g');
    vehicleEl.setAttribute('id', 'vehicleMarker');
    vehicleEl.style.display = 'none';
    const vCircle = document.createElementNS(ns, 'circle');
    vCircle.setAttribute('r', '9');
    vCircle.setAttribute('fill', '#FF4757');
    vCircle.setAttribute('stroke', '#fff');
    vCircle.setAttribute('stroke-width', '2');
    const vPulse = document.createElementNS(ns, 'circle');
    vPulse.setAttribute('r', '9');
    vPulse.setAttribute('fill', 'none');
    vPulse.setAttribute('stroke', '#FF4757');
    vPulse.setAttribute('stroke-width', '2');
    vPulse.setAttribute('opacity', '0.6');
    const anim = document.createElementNS(ns, 'animate');
    anim.setAttribute('attributeName', 'r');
    anim.setAttribute('values', '9;18;9');
    anim.setAttribute('dur', '1.6s');
    anim.setAttribute('repeatCount', 'indefinite');
    const animOpacity = document.createElementNS(ns, 'animate');
    animOpacity.setAttribute('attributeName', 'opacity');
    animOpacity.setAttribute('values', '0.6;0;0.6');
    animOpacity.setAttribute('dur', '1.6s');
    animOpacity.setAttribute('repeatCount', 'indefinite');
    vPulse.appendChild(anim);
    vPulse.appendChild(animOpacity);
    vehicleEl.appendChild(vPulse);
    vehicleEl.appendChild(vCircle);
    svgEl.appendChild(vehicleEl);

    container.innerHTML = '';
    container.appendChild(svgEl);
  }

  function edgeKey(a, b) {
    return [a, b].sort().join('__');
  }

  function highlightRoute(pathNodes) {
    currentRoutePath = pathNodes;
    // reset all edges
    svgEl.querySelectorAll('line').forEach(line => {
      line.setAttribute('stroke', '#1D2530');
      line.setAttribute('stroke-width', '5');
    });
    for (let i = 0; i < pathNodes.length - 1; i++) {
      const key = edgeKey(pathNodes[i], pathNodes[i + 1]);
      const line = svgEl.querySelector(`line[data-edge-key="${key}"]`);
      if (line) {
        line.setAttribute('stroke', '#16E0A6');
        line.setAttribute('stroke-width', '6');
      }
    }
    // show vehicle at the start node
    if (pathNodes.length) {
      moveVehicleTo(pathNodes[0]);
      vehicleEl.style.display = 'block';
    }
  }

  function moveVehicleTo(nodeId) {
    const node = nodeById(nodeId);
    if (!node || !vehicleEl) return;
    vehicleEl.setAttribute('transform', `translate(${node.x}, ${node.y})`);
  }

  function setJunctionState(nodeId, isPriority) {
    const dot = svgEl.querySelector(`#dot-${nodeId}`);
    if (!dot) return;
    if (isPriority) {
      dot.setAttribute('fill', '#16E0A6');
      dot.setAttribute('r', '9');
    } else {
      const node = nodeById(nodeId);
      const isTerminal = node.type === 'source' || node.type === 'destination';
      dot.setAttribute('fill', isTerminal ? '#4CC9F0' : '#7C8798');
      dot.setAttribute('r', isTerminal ? 10 : 7);
    }
  }

  function resetAllSignals() {
    if (!networkData) return;
    networkData.nodes.forEach(n => setJunctionState(n.id, false));
  }

  function hideVehicle() {
    if (vehicleEl) vehicleEl.style.display = 'none';
  }

  return {
    loadNetwork, render, highlightRoute, moveVehicleTo,
    setJunctionState, resetAllSignals, hideVehicle,
    getNetwork: () => networkData,
  };
})();
