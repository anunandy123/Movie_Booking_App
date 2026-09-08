const map = document.querySelector('#seat-map');
const selection = document.querySelector('#selection');
const reserveButton = document.querySelector('#reserve');
const confirmButton = document.querySelector('#confirm');
const timer = document.querySelector('#timer');
const message = document.querySelector('#message');
const showSelect = document.querySelector('#show-select');
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
let seats = [];
let selected = new Set();
let reservationId = null;
let expiresAt = null;
let stripe = null;
let stripeElements = null;
let paymentElement = null;
let showId = new URLSearchParams(window.location.search).get('show_id') || showSelect?.value || '';
if (window.SMARTSEAT_STRIPE_KEY && window.Stripe) stripe = Stripe(window.SMARTSEAT_STRIPE_KEY);

async function request(url, options = {}) {
  const response = await fetch(url, {headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken}, ...options});
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    throw new Error(response.status === 401 ? 'Sign in before starting payment.' : `Request failed (${response.status}).`);
  }
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
  reserveButton.disabled = !labels.length || !showId;
}

showSelect?.addEventListener('change', () => {
  showId = showSelect.value;
  reservationId = null;
  expiresAt = null;
  selected.clear();
  confirmButton.disabled = true;
  message.textContent = showId ? 'Show selected. Choose your seats.' : 'Choose a show before selecting seats.';
  refresh();
});

async function refresh() {
  if (!showId) { seats = []; render(); return; }
  try { seats = (await request(`/api/seats/?show_id=${encodeURIComponent(showId)}`)).seats; render(); } catch (error) { message.textContent = error.message; }
}

reserveButton.onclick = async () => {
  try {
    if (!showId) throw new Error('Choose a show before reserving seats.');
    const payload = {seat_ids: [...selected], show_id: Number(showId)};
    const data = await request(reservationId ? `/api/reservations/${reservationId}/` : '/api/reservations/', {method: reservationId ? 'PATCH' : 'POST', body: JSON.stringify(payload)});
    reservationId = data.reservation_id; expiresAt = new Date(data.expires_at); confirmButton.disabled = false; message.textContent = 'Seats held. Enter payment details to continue.'; await refresh();
  } catch (error) { message.textContent = error.message; await refresh(); }
};

confirmButton.onclick = async () => {
  try {
    const payment = await request(`/api/reservations/${reservationId}/payment/`, {method: 'POST', body: JSON.stringify({})});
    if (!stripe || !payment.client_secret) throw new Error('Online payment is not configured for this environment.');
    if (!stripeElements) {
      stripeElements = stripe.elements({clientSecret: payment.client_secret});
      paymentElement = stripeElements.create('payment');
      paymentElement.mount('#payment-element');
      message.textContent = 'Payment form loaded. Click Complete payment again.';
      return;
    }
    const result = await stripe.confirmPayment({elements: stripeElements, redirect: 'if_required'});
    if (result.error) throw new Error(result.error.message);
    await request(`/api/reservations/${reservationId}/confirm/`, {method: 'POST'});
    message.textContent = 'Payment verified. Your seats are confirmed.'; confirmButton.disabled = true; reserveButton.disabled = true; await refresh();
  }
  catch (error) { message.textContent = error.message; }
};

setInterval(() => { if (!expiresAt) return; const seconds = Math.max(0, Math.floor((expiresAt - new Date()) / 1000)); timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; if (!seconds) { expiresAt = null; reservationId = null; confirmButton.disabled = true; refresh(); } }, 1000);
setInterval(refresh, 10000);
refresh();