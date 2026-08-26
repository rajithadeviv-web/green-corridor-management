/*
traffic.js
-----------
Runs the live AI congestion prediction (real backend ML call) and renders
the result with model confidence + explanation. Also runs route
calculation and renders route option cards. Handles the traffic-event
modal that triggers dynamic recalculation.
*/

function randomTrafficSample() {
  const hour = new Date().getHours();
  const dayOfWeek = new Date().getDay();
  const roadCapacity = 1800;
  const isRush = (hour >= 7 && hour <= 10) || (hour >= 17 && hour <= 20);
  const vehicleCount = Math.round(roadCapacity * (isRush ? (0.7 + Math.random() * 0.5) : (0.25 + Math.random() * 0.35)));
  const roadLength = 2.4;
  const averageSpeed = Math.max(6, Math.round(55 - (vehicleCount / roadCapacity) * 40 + (Math.random() * 6 - 3)));
  const weatherOptions = ['clear', 'clear', 'clear', 'rain', 'fog'];
  const weather = weatherOptions[Math.floor(Math.random() * weatherOptions.length)];

  return {
    vehicle_count: vehicleCount,
    traffic_density: Math.round((vehicleCount / roadLength) * 100) / 100,
    average_speed: averageSpeed,
    road_length: roadLength,
    hour,
    day_of_week: dayOfWeek,
    weather,
    road_capacity: roadCapacity,
  };
}

async function runTrafficPrediction() {
  const badge = document.getElementById('aiBadge');
  badge.textContent = 'PREDICTING…';

  const features = randomTrafficSample();
  features.request_id = window.AppState.currentRequestId;

  try {
    const res = await fetch('/api/traffic/predict', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(features),
    });
    const data = await res.json();
    if (!data.success) {
      badge.textContent = 'ERROR';
      logActivity(`AI prediction failed: ${data.error}`, 'error');
      return null;
    }
    renderPrediction(data.prediction, features);
    badge.textContent = 'LIVE';
    logActivity(`AI predicted ${data.prediction.predicted_congestion.toUpperCase()} congestion (confidence ${(data.prediction.confidence * 100).toFixed(1)}%)`);
    window.AppState.lastPrediction = data.prediction;
    return data.prediction;
  } catch (e) {
    badge.textContent = 'ERROR';
    console.error(e);
    return null;
  }
}

function renderPrediction(prediction, features) {
  const body = document.getElementById('aiPanelBody');
  const level = prediction.predicted_congestion;
  const reasons = prediction.explanation.map(r => `<li>${r}</li>`).join('');

  body.innerHTML = `
    <div class="ai-result">
      <span class="congestion-tag congestion-${level}">${level.toUpperCase()}</span>
      <div>
        <span class="muted-note">Model confidence: ${(prediction.confidence * 100).toFixed(1)}% &nbsp;·&nbsp; Score: ${prediction.congestion_score}/100</span>
        <div class="confidence-bar-track"><div class="confidence-bar-fill" style="width:${prediction.confidence * 100}%"></div></div>
      </div>
      <div>
        <span class="muted-note">Why:</span>
        <ul class="reason-list">${reasons}</ul>
      </div>
      <div>
        <span class="muted-note">Inputs — vehicles: ${features.vehicle_count}, density: ${features.traffic_density}/km,
        speed: ${features.average_speed} km/h, weather: ${features.weather}</span>
      </div>
    </div>
  `;
}

async function runRouteCalculation() {
  const req = window.AppState.currentRequest;
  const congestionHint = window.AppState.lastPrediction
    ? window.AppState.lastPrediction.predicted_congestion
    : 'medium';

  try {
    const res = await fetch('/api/routes/calculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: window.AppState.currentRequestId,
        source: req.source_node,
        destination: req.destination_node,
        congestion_level: congestionHint,
      }),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Route calculation failed: ${data.error}`, 'error');
      return;
    }
    renderRoutes(data.routes);
    window.AppState.selectedRoute = data.recommended;
    logActivity(`${data.routes.length} candidate routes evaluated. Recommended route score: ${data.recommended.total_score}`);

    // Activate the corridor automatically on the recommended route
    await activateCorridor(data.recommended);

  } catch (e) {
    console.error(e);
    logActivity('Route calculation request failed.', 'error');
  }
}

function renderRoutes(routes) {
  const body = document.getElementById('routesPanelBody');
  body.innerHTML = routes.map(r => `
    <div class="route-card ${r.is_recommended ? 'recommended' : ''}">
      <div class="route-card-head">
        <strong>${r.is_recommended ? '★ Recommended Route' : 'Alternative Route ' + r.rank}</strong>
        <span class="score-pill">score ${r.total_score}</span>
      </div>
      <div class="route-meta">
        <span>Distance: <b>${r.distance_km} km</b></span>
        <span>ETA: <b>${r.estimated_travel_time_min} min</b></span>
        <span>Signals: <b>${r.num_intersections}</b></span>
        <span>Congestion: <b>${r.congestion_level}</b></span>
      </div>
      <div class="muted-note" style="margin-top:6px;">${r.path_labels.join(' → ')}</div>
    </div>
  `).join('');
}

/* ---------------- Traffic event modal ---------------- */

document.getElementById('eventBtn').addEventListener('click', () => {
  document.getElementById('eventModal').classList.remove('hidden');
});
document.getElementById('eventCancelBtn').addEventListener('click', () => {
  document.getElementById('eventModal').classList.add('hidden');
});

document.getElementById('eventConfirmBtn').addEventListener('click', async () => {
  const eventType = document.getElementById('eventType').value;
  const location = document.getElementById('eventLocation').value;
  document.getElementById('eventModal').classList.add('hidden');

  try {
    const res = await fetch('/api/traffic/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: window.AppState.currentRequestId,
        event_type: eventType,
        location_node: location,
      }),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Traffic event failed: ${data.error}`, 'error');
      return;
    }
    logActivity(`⚠ Traffic event: ${data.message}`, 'warning');
    await recalculateAfterEvent();
  } catch (e) {
    console.error(e);
  }
});

async function recalculateAfterEvent() {
  const req = window.AppState.currentRequest;
  try {
    const res = await fetch('/api/corridor/recalculate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        request_id: window.AppState.currentRequestId,
        source: req.source_node,
        destination: req.destination_node,
      }),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Recalculation failed: ${data.error}`, 'error');
      return;
    }
    renderRoutes(data.routes);
    window.AppState.selectedRoute = data.recommended;
    logActivity(`Route recalculated. New recommended route score: ${data.recommended.total_score}`);
    renderSignals(data.signal_states);
    GreenCorridorMap.resetAllSignals();
    GreenCorridorMap.highlightRoute(data.recommended.path_nodes);
    data.signal_states.forEach(s => GreenCorridorMap.setJunctionState(s.junction_id, true));
  } catch (e) {
    console.error(e);
  }
}
