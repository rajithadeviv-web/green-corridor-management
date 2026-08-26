/*
emergency.js
-------------
Handles the "New Emergency Request" form and the one-click Demo Scenario
button, both of which drive the full pipeline: create request -> AI
prediction -> route calculation -> corridor activation.
*/

document.getElementById('emergencyForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const payload = {
    vehicle_id: document.getElementById('vehicleId').value.trim(),
    vehicle_type: document.getElementById('vehicleType').value,
    source: document.getElementById('sourceNode').value,
    destination: document.getElementById('destinationNode').value,
    emergency_level: document.getElementById('emergencyLevel').value,
  };
  await dispatchEmergency(payload);
});

document.getElementById('demoBtn').addEventListener('click', async () => {
  const vehicleId = `AMB-${Math.floor(100 + Math.random() * 900)}`;
  document.getElementById('vehicleId').value = vehicleId;
  document.getElementById('sourceNode').value = 'hospital';
  document.getElementById('destinationNode').value = 'care_center';
  document.getElementById('emergencyLevel').value = 'critical';

  await dispatchEmergency({
    vehicle_id: vehicleId,
    vehicle_type: 'ambulance',
    source: 'hospital',
    destination: 'care_center',
    emergency_level: 'critical',
  });
});

async function dispatchEmergency(payload) {
  try {
    const res = await fetch('/api/emergency/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.success) {
      logActivity(`Emergency request rejected: ${data.error}`, 'error');
      alert(`Request rejected: ${data.error}`);
      return;
    }

    window.AppState.currentRequestId = data.request.id;
    window.AppState.currentRequest = data.request;
    logActivity(`Emergency request #${data.request.id} created for ${data.request.vehicle_id} (${data.request.emergency_level.toUpperCase()})`);

    await runTrafficPrediction(payload);
    await runRouteCalculation(payload);

    document.getElementById('advanceBtn').disabled = false;
    document.getElementById('eventBtn').disabled = false;
    document.getElementById('completeBtn').disabled = false;

  } catch (err) {
    console.error(err);
    logActivity('Failed to dispatch emergency request. See console.', 'error');
  }
}
