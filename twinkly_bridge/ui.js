/* Merge rapid adjustments and reject status responses from before a user's action. */
class ControlQueue {
  constructor(send, onState, onError) {
    this.send = send; this.onState = onState; this.onError = onError;
    this.state = {mode:'restore', color:'#ff4080', brightness:30, speed:1, pattern:'mirror', gain:1};
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
if (typeof module !== 'undefined') module.exports = {ControlQueue};
if (typeof document !== 'undefined') {
  const $ = id => document.getElementById(id);
  async function request(path, data) {
    const response = await fetch(path, {method:data?'POST':'GET', headers:data?{'Content-Type':'application/json'}:{}, body:data?JSON.stringify(data):undefined});
    const value = await response.json();
    if (!response.ok) throw Error(value.error || 'Kunne ikke kontakte addon’en');
    return value;
  }
  const controls = new ControlQueue(patch => request('api/control', patch), state => {
    document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('selected', b.dataset.mode === state.mode));
    document.querySelectorAll('[data-pattern]').forEach(b => b.classList.toggle('selected', b.dataset.pattern === state.pattern));
    for (const id of ['color','brightness','speed','gain']) $(id).value = state[id];
    $('brightnessValue').textContent = state.brightness+'%';
    $('speedValue').textContent = state.speed+'×';
    $('gainValue').textContent = state.gain+'×';
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
      $('source').textContent = source.connected ? 'Sendspin forbundet'+(source.group?' · '+source.group:'')+'\n'+(s.audio_fresh?'Modtager visualiseringsdata':source.clock_synced?'Venter på musik fra gruppen':'Synkroniserer ur…') : source.state === 'disabled' ? 'Angiv sendspin_url under konfiguration' : 'Sendspin: '+(source.state||'venter');
      $('error').textContent = [s.error, source.error].filter(Boolean).join('\n');
      $('diagnostics').textContent = 'Ønsket: '+s.mode+' · Aktiv: '+s.applied_mode+' · Gendannet realtime: '+s.recoveries+' · Frames: '+(source.frames_rendered||0);
    } catch (error) { $('error').textContent = error.message; }
    finally { refreshing = false; }
  }
  document.querySelectorAll('[data-mode]').forEach(b => b.addEventListener('click', () => controls.change({mode:b.dataset.mode})));
  document.querySelectorAll('[data-pattern]').forEach(b => b.addEventListener('click', () => controls.change({mode:'music', pattern:b.dataset.pattern})));
  for (const id of ['color','brightness','speed','gain']) {
    $(id).addEventListener('change', () => controls.change({[id]:id === 'color'?$(id).value:Number($(id).value)}));
    if (id !== 'color') $(id).addEventListener('input', () => { $(id+'Value').textContent = $(id).value+(id === 'brightness'?'%':'×'); });
  }
  refresh(); setInterval(refresh, 2000);
}
