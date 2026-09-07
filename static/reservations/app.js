const map = document.querySelector('#seat-map');
const selection = document.querySelector('#selection');
const reserveButton = document.querySelector('#reserve');
const confirmButton = document.querySelector('#confirm');
const timer = document.querySelector('#timer');
const message = document.querySelector('#message');
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
let seats = [];
let selected = new Set();
let reservationId = null;
let expiresAt = null;

async function request(url, options = {}) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken}, ...options});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong.');
  return data;
}

function render() {
  map.innerHTML = '';
  seats.forEach(seat => {
    const button = document.createElement('button');
    button.className = `seat ${seat.status}`;
    button.textContent = seat.label;
    button.disabled = seat.status === 'booked';
    button.onclick = () => { selected.has(seat.id) ? selected.delete(seat.id) : selected.add(seat.id); render(); };
    map.appendChild(button);
  });
  const labels = seats.filter(seat => selected.has(seat.id)).map(seat => seat.label);
  selection.innerHTML = labels.length ? `<strong>${labels.join('  ·  ')}</strong>` : '<span>No seats selected</span>';
  reserveButton.disabled = !labels.length;
}

async function refresh() {
  try { seats = (await request('/api/seats/')).seats; render(); } catch (error) { message.textContent = error.message; }
}

reserveButton.onclick = async () => {
  try {
    const data = await request(reservationId ? `/api/reservations/${reservationId}/` : '/api/reservations/', {method: reservationId ? 'PATCH' : 'POST', body: JSON.stringify({seat_ids: [...selected]})});
    reservationId = data.reservation_id; expiresAt = new Date(data.expires_at); confirmButton.disabled = false; message.textContent = 'Seats held. You can still change your selection.'; await refresh();
  } catch (error) { message.textContent = error.message; await refresh(); }
};

confirmButton.onclick = async () => {
  try { await request(`/api/reservations/${reservationId}/confirm/`, {method: 'POST'}); message.textContent = 'Payment complete. Your seats are confirmed.'; confirmButton.disabled = true; reserveButton.disabled = true; await refresh(); }
  catch (error) { message.textContent = error.message; }
};

setInterval(() => { if (!expiresAt) return; const seconds = Math.max(0, Math.floor((expiresAt - new Date()) / 1000)); timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; if (!seconds) { expiresAt = null; reservationId = null; confirmButton.disabled = true; refresh(); } }, 1000);
setInterval(refresh, 10000);
refresh();