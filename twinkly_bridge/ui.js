/* Merge rapid adjustments and reject status responses from before a user's action. */
async function readApiResponse(response) {
  const body = await response.text();
  let value;
  try { value = JSON.parse(body); } catch (_) {
    throw Error('Kunne ikke hente addon-status (HTTP '+response.status+'). Svaret var ikke JSON. Prøv at åbne webgrænsefladen igen.');
  }
  if (!response.ok) throw Error(value?.error || 'Kunne ikke kontakte addon’en (HTTP '+response.status+').');
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Addon’en returnerede et ugyldigt statussvar.');
  return value;
}
class ControlQueue {
  constructor(send, onState, onError) {
    this.send = send; this.onState = onState; this.onError = onError;
    this.state = {mode:'restore', color:'#ff4080', brightness:30, speed:1, pattern:'mirror', gain:1, punch:50, cover_colors:false, light_delay_ms:0};
    this.pending = null; this.sending = false; this.epoch = 0; this.revision = -1;
  }
  accept(status, epoch) {
    if (epoch !== this.epoch || this.sending || this.pending || status.revision < this.revision) return false;
    this.revision = status.revision;
    for (const key of Object.keys(this.state)) if (status[key] !== undefined) this.state[key] = status[key];
    this.onState(this.state); return true;
  }
  change(patch) {
    this.epoch++; Object.assign(this.state, patch);
    this.pending = Object.assign(this.pending || {}, patch);
    this.onState(this.state);
    return this.flush();
  }
  async flush() {
    if (this.sending) return;
    this.sending = true;
    try {
      while (this.pending) {
        const patch = this.pending; this.pending = null;
        try {
          const response = await this.send(patch);
          this.revision = Math.max(this.revision, response.revision);
        } catch (error) { this.onError(error); }
      }
    } finally { this.sending = false; }
  }
}
function sourceDescription(s) {
  const source = s.sendspin || {};
  if (!source.connected) return source.state === 'disabled' ? 'Angiv sendspin_url under konfiguration' : 'Sendspin: '+(source.state||'venter');
  const signal = (s.spectrum_fresh ?? s.audio_fresh) ? 'Modtager visualiseringsdata' : s.bass_fresh ? 'Modtager PCM-lyd · spektrum mangler; baspuls fortsætter' : source.clock_synced ? 'Venter på musik fra gruppen' : 'Synkroniserer ur…';
  return 'Sendspin forbundet'+(source.group?' · '+source.group:'')+'\n'+signal;
}
if (typeof module !== 'undefined') module.exports = {ControlQueue, readApiResponse, sourceDescription};
if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  async function request(path, data) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch(path, {signal:controller.signal, method:data?'POST':'GET', headers:data?{'Content-Type':'application/json'}:{}, body:data?JSON.stringify(data):undefined});
      return await readApiResponse(response);
    } catch (error) {
      if (error.name === 'AbortError') throw Error('Statusforespørgslen tog for lang tid. Prøv at åbne webgrænsefladen igen.');
      throw error;
    } finally { clearTimeout(timeout); }
  }
  const controls = new ControlQueue(patch => request('api/control', patch), state => {
    document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('selected', b.dataset.mode === state.mode));
    document.querySelectorAll('[data-pattern]').forEach(b => b.classList.toggle('selected', b.dataset.pattern === state.pattern));
    for (const id of ['color','brightness','speed','gain','punch','light_delay_ms']) $(id).value = state[id];
    $('coverColors').checked = state.cover_colors;
    $('brightnessValue').textContent = state.brightness+'%';
    $('speedValue').textContent = state.speed+'×';
    $('gainValue').textContent = state.gain+'×';
    $('punchValue').textContent = state.punch+'%';
    $('light_delay_msValue').textContent = state.light_delay_ms+' ms';
  }, error => { $('error').textContent = error.message; });
  let refreshing = false;
  async function refresh() {
    if (refreshing) return;
    refreshing = true; const epoch = controls.epoch;
    try {
      const s = await request('api/status');
      controls.accept(s, epoch);
      // Status from before a command must not announce its old mode or clear errors.
      if (epoch !== controls.epoch || s.revision < controls.revision) return;
      $('status').textContent = (s.connected?'Twinkly forbundet · '+s.leds+' LED':'Twinkly ikke forbundet')+'\n'+(s.device_ip||'Angiv device_ip under konfiguration');
      const source = s.sendspin || {};
      $('source').textContent = sourceDescription(s);
      $('error').textContent = [s.error, source.error].filter(Boolean).join('\n');
      $('diagnostics').textContent = 'Ønsket: '+s.mode+' · Aktiv: '+s.applied_mode+' · Gendannet realtime: '+s.recoveries+' · Frames: '+(source.frames_rendered||0)+(source.roles?.includes('player@v1')?' · Lydpakker: '+(source.audio_chunks_received||0)+' (uden lydudgang)':'')+(s.bass_fresh?' · PCM-bas aktiv · Basanslag: '+(s.bass_hits||0):s.spectrum_fresh?' · Spektrum-bas':' · Intet aktuelt lydsignal');
    } catch (error) {
      $('error').textContent = error.message;
      $('status').textContent = 'Aktuel status kunne ikke hentes';
      $('source').textContent = 'Sendspin-status ukendt – forbindelsen kan stadig være aktiv';
      $('diagnostics').textContent = 'Ingen aktuelle målinger; den tidligere frame-tæller er ikke længere bekræftet';
    }
    finally { refreshing = false; }
  }
  $('coverColors').addEventListener('change', () => controls.change({cover_colors:$('coverColors').checked}));
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => controls.change({mode:b.dataset.mode})));
  document.querySelectorAll('[data-pattern]').forEach(b => b.addEventListener('click', () => controls.change({mode:'music', pattern:b.dataset.pattern})));
  let punchTimer = null;
  for (const id of ['color','brightness','speed','gain','punch','light_delay_ms']) {
    $(id).addEventListener('change', () => {
      if (id === 'punch') { clearTimeout(punchTimer); punchTimer = null; }
      controls.change({[id]:id === 'color'?$(id).value:Number($(id).value)});
    });
    if (id !== 'color') $(id).addEventListener('input', () => {
      $(id+'Value').textContent = $(id).value+(id==='light_delay_ms'?' ms':['brightness','punch'].includes(id)?'%':'×');
      if (id === 'punch' && punchTimer === null) punchTimer = setTimeout(() => {
        punchTimer = null; controls.change({punch:Number($('punch').value)});
      }, 100);
    });
  }
  refresh(); setInterval(refresh, 2000);
}
