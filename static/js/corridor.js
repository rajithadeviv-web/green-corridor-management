/*
corridor.js
------------
Activates the simulated green corridor on the recommended route, renders
signal states, and drives the "Advance Vehicle" / "Complete & Release"
buttons that step the simulation forward.
*/

async function activateCorridor(route) {
  try {
    const res = await fetch('/api/corridor/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: window.AppState.currentRequestId,
        junctions: route.junctions,
        path_nodes: route.path_nodes,
        distance_km: route.distance_km,
        estimated_travel_time_min: route.estimated_travel_time_min,
      }),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Corridor activation failed: ${data.error}`, 'error');
      return;
    }

    document.getElementById('vehicleBadge').textContent = 'CORRIDOR ACTIVE';
    document.getElementById('vehicleBadge').className = 'badge badge-active';

    GreenCorridorMap.resetAllSignals();
    GreenCorridorMap.highlightRoute(route.path_nodes);
    data.signal_states.forEach(s => GreenCorridorMap.setJunctionState(s.junction_id, true));

    renderSignals(data.signal_states);
    renderVehicleState(data.vehicle_state);

    logActivity(`Green corridor activated across ${route.junctions.length} junction(s). ${data.simulation_mode}`);
  } catch (e) {
    console.error(e);
    logActivity('Corridor activation request failed.', 'error');
  }
}

function renderSignals(states) {
  const body = document.getElementById('signalsPanelBody');
  const network = GreenCorridorMap.getNetwork();
  if (!states.length) {
    body.innerHTML = '<p class="muted-note">No active corridor.</p>';
    return;
  }
  body.innerHTML = states.map((s, i) => {
    const node = network.nodes.find(n => n.id === s.junction_id);
    const label = node ? node.label : s.junction_id;
    const isPriority = s.is_priority !== undefined ? s.is_priority : s.state === 'priority_green';
    return `
      <div class="signal-row">
        <span class="signal-name"><span class="light ${isPriority ? 'light-green' : 'light-normal'}"></span>${label}</span>
        <span class="muted-note">${isPriority ? 'PRIORITY GREEN' : 'NORMAL'}</span>
      </div>
    `;
  }).join('');
}

function renderVehicleState(state) {
  if (!state) return;
  const network = GreenCorridorMap.getNetwork();
  const currentNode = network.nodes.find(n => n.id === state.current_node);
  const nextNode = state.next_node ? network.nodes.find(n => n.id === state.next_node) : null;

  document.getElementById('vCurrent').textContent = currentNode ? currentNode.label : '—';
  document.getElementById('vNext').textContent = nextNode ? nextNode.label : 'Arrived';
  document.getElementById('vDistance').textContent = `${state.distance_remaining_km} km`;
  document.getElementById('vEta').textContent = `${state.eta_minutes} min`;

  GreenCorridorMap.moveVehicleTo(state.current_node);

  if (state.status === 'completed') {
    document.getElementById('advanceBtn').disabled = true;
    document.getElementById('vehicleBadge').textContent = 'ARRIVED';
  }
}

document.getElementById('advanceBtn').addEventListener('click', async () => {
  if (!window.AppState.currentRequestId) return;
  try {
    const res = await fetch('/api/vehicle/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ request_id: window.AppState.currentRequestId }),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Vehicle simulation failed: ${data.error}`, 'error');
      return;
    }
    renderVehicleState(data.vehicle_state);
    logActivity(`Vehicle advanced to ${data.vehicle_state.current_node_label}. Signal there released back to normal after passing.`);

    // reflect signal release on the map + panel
    GreenCorridorMap.setJunctionState(data.vehicle_state.current_node, false);
    refreshSignalPanel();
  } catch (e) {
    console.error(e);
  }
});

async function refreshSignalPanel() {
  if (!window.AppState.currentRequestId) return;
  const res = await fetch(`/api/corridor/status/${window.AppState.currentRequestId}`);
  const data = await res.json();
  if (data.success) renderSignals(data.signal_states);
}

document.getElementById('completeBtn').addEventListener('click', async () => {
  const route = window.AppState.selectedRoute;
  if (!route || !window.AppState.currentRequestId) return;

  const baselineTime = route.base_travel_time_min * 1.6; // rough "without corridor" baseline for demo purposes
  const actualTime = route.estimated_travel_time_min;
  const timeSaved = Math.max(0, Math.round((baselineTime - actualTime) * 10) / 10);

  try {
    const res = await fetch('/api/corridor/release', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: window.AppState.currentRequestId,
        junctions: route.junctions,
        total_time_min: actualTime,
        time_saved_min: timeSaved,
      }),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Corridor release failed: ${data.error}`, 'error');
      return;
    }
    logActivity(`✓ Corridor released. Trip complete — estimated time saved: ${timeSaved} min. Normal traffic resumed.`);

    GreenCorridorMap.resetAllSignals();
    GreenCorridorMap.hideVehicle();
    document.getElementById('vehicleBadge').textContent = 'NO ACTIVE TRIP';
    document.getElementById('vehicleBadge').className = 'badge';
    document.getElementById('advanceBtn').disabled = true;
    document.getElementById('eventBtn').disabled = true;
    document.getElementById('completeBtn').disabled = true;
    document.getElementById('signalsPanelBody').innerHTML = '<p class="muted-note">No active corridor.</p>';
    document.getElementById('vCurrent').textContent = '—';
    document.getElementById('vNext').textContent = '—';
    document.getElementById('vDistance').textContent = '—';
    document.getElementById('vEta').textContent = '—';

    refreshDashboardStats();

    window.AppState.currentRequestId = null;
    window.AppState.currentRequest = null;
    window.AppState.selectedRoute = null;
  } catch (e) {
    console.error(e);
  }
});
