/*
dashboard.js
-------------
Shared application state + activity log + summary stat polling + clock.
Other JS files (emergency.js, traffic.js, corridor.js) attach to window.AppState.
*/

window.AppState = {
  currentRequestId: null,
  currentRequest: null,
  selectedRoute: null,
  networkLoaded: false,
};

function logActivity(message, level = 'info') {
  const list = document.getElementById('activityLog');
  const entry = document.createElement('div');
  entry.className = 'log-entry';
  const time = new Date().toLocaleTimeString();
  entry.innerHTML = `<span class="log-time">${time}</span><span>${message}</span>`;
  list.appendChild(entry);
  list.scrollTop = list.scrollHeight;
}

function updateClock() {
  document.getElementById('liveClock').textContent = new Date().toLocaleTimeString();
}
setInterval(updateClock, 1000);
updateClock();

async function refreshDashboardStats() {
  try {
    const res = await fetch('/api/dashboard');
    const data = await res.json();
    if (!data.success) return;

    const s = data.stats;
    document.getElementById('statActiveVehicles').textContent = s.active_vehicles;
    document.getElementById('statActiveCorridors').textContent = s.active_corridors;
    document.getElementById('statTimeSaved').innerHTML = `${s.avg_time_saved_min}<small>min</small>`;
    document.getElementById('statSignalsPrioritized').textContent = s.signals_prioritized;
    document.getElementById('statCompleted').textContent = s.completed_trips;

    const chip = document.getElementById('modelStatusChip');
    if (data.model_loaded) {
      chip.innerHTML = '<span class="dot dot-green"></span> ML MODEL: LOADED (RandomForest)';
    } else {
      chip.innerHTML = '<span class="dot dot-red"></span> ML MODEL: NOT LOADED';
    }
  } catch (e) {
    console.error('Failed to refresh dashboard stats', e);
  }
}

document.getElementById('clearLogBtn').addEventListener('click', () => {
  document.getElementById('activityLog').innerHTML = '';
});

// Initial load
document.addEventListener('DOMContentLoaded', async () => {
  await GreenCorridorMap.loadNetwork();
  GreenCorridorMap.render('mapContainer');
  populateNodeSelectors();
  refreshDashboardStats();
  setInterval(refreshDashboardStats, 5000);
  logActivity('Command center initialized. Simulated road network loaded.');
});

function populateNodeSelectors() {
  const network = GreenCorridorMap.getNetwork();
  const sourceSel = document.getElementById('sourceNode');
  const destSel = document.getElementById('destinationNode');
  const eventLocSel = document.getElementById('eventLocation');

  network.nodes.forEach(n => {
    const opt1 = new Option(n.label, n.id);
    const opt2 = new Option(n.label, n.id);
    const opt3 = new Option(n.label, n.id);
    sourceSel.add(opt1);
    destSel.add(opt2);
    eventLocSel.add(opt3);
  });

  // sensible defaults for the demo scenario
  sourceSel.value = 'hospital';
  destSel.value = 'care_center';
}
