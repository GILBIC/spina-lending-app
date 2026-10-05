/** Private in-memory drawing input. Nothing is uploaded until the parent saves. */
export function mountOfficeSignatureInput({root, fileInput, onChange = () => {}}) {
  let disposed = false, disabled = false, mode = 'paper_scan', context;
  let strokes = [], active = null, revision = 0, image = null;
  const removers = [];
  const fileLabel = fileInput.closest('label');
  root.innerHTML = `<div class="office-signature-input">
    <div class="action-row"><button type="button" class="button button-primary" data-signature-screen aria-pressed="false">Sign on screen</button><button type="button" class="button button-outline" data-signature-paper aria-pressed="true">Upload signed paper</button></div>
    <div data-signature-drawing hidden>
      <p>Applicant: review the information above, then sign in the box using your finger, a pen, or a mouse.</p>
      <canvas data-signature-canvas width="960" height="480" aria-label="Applicant signature drawing area">Use Upload signed paper if drawing is unavailable.</canvas>
      <div class="action-row"><button type="button" class="button button-outline" data-signature-clear>Clear signature</button></div>
    </div><p data-signature-status role="status" aria-live="polite"></p>
  </div>`;
  const canvas = root.querySelector('[data-signature-canvas]');
  const drawing = root.querySelector('[data-signature-drawing]');
  const screen = root.querySelector('[data-signature-screen]');
  const paper = root.querySelector('[data-signature-paper]');
  const clearButton = root.querySelector('[data-signature-clear]');
  const status = root.querySelector('[data-signature-status]');
  canvas.width = 960; canvas.height = 480;
  function listen(element, event, callback) {
    element.addEventListener(event, callback);
    removers.push(() => element.removeEventListener(event, callback));
  }
  function changed() { revision++; image = null; onChange(); }
  function paint() {
    if (!context) return;
    context.fillStyle = '#ffffff'; context.fillRect(0, 0, canvas.width, canvas.height);
    context.strokeStyle = '#171717'; context.lineWidth = 3; context.lineCap = 'round'; context.lineJoin = 'round';
    for (const stroke of strokes) {
      if (!stroke.length) continue;
      context.beginPath(); context.moveTo(stroke[0].x, stroke[0].y);
      for (const point of stroke.slice(1)) context.lineTo(point.x, point.y);
      context.stroke();
    }
  }
  function release() {
    const pointer = active; active = null;
    if (pointer) { try { canvas.releasePointerCapture?.(pointer.id); } catch { /* Pointer already ended. */ } }
  }
  function select(value) {
    if (disposed || disabled || mode === value) return;
    if (value === 'screen_signature') {
      context = canvas.getContext?.('2d');
      if (!context) { status.textContent = 'Drawing is unavailable in this browser. Upload a signed paper copy.'; return; }
    }
    release(); mode = value;
    drawing.hidden = mode !== 'screen_signature'; fileLabel.hidden = mode !== 'paper_scan';
    fileInput.required = mode === 'paper_scan';
    screen.setAttribute('aria-pressed', String(mode === 'screen_signature'));
    paper.setAttribute('aria-pressed', String(mode === 'paper_scan'));
    status.textContent = mode === 'screen_signature' ? 'The applicant can sign in the box. Then confirm that you witnessed the signature.' : 'Choose the signed paper copy below.';
    paint(); changed();
  }
  function point(event) {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return null;
    return {x:Math.min(canvas.width, Math.max(0, (event.clientX - rect.left) * canvas.width / rect.width)), y:Math.min(canvas.height, Math.max(0, (event.clientY - rect.top) * canvas.height / rect.height))};
  }
  function down(event) {
    if (disposed || disabled || mode !== 'screen_signature' || active || event.isPrimary === false || event.button !== 0) return;
    const p = point(event); if (!p) return;
    event.preventDefault(); const stroke = [p]; strokes.push(stroke); active = {id:event.pointerId,stroke};
    canvas.setPointerCapture?.(event.pointerId); changed(); paint();
  }
  function move(event) {
    if (disposed || disabled || !active || active.id !== event.pointerId) return;
    const p = point(event); if (!p) return;
    event.preventDefault(); active.stroke.push(p); changed(); paint();
  }
  function end(event) {
    if (disposed || !active || active.id !== event.pointerId) return;
    move(event); release(); status.textContent = 'Signature drawn. Check it before saving; use Clear signature to start again.';
  }
  function cancel(event) {
    if (disposed || !active || active.id !== event.pointerId) return;
    strokes = strokes.filter(stroke => stroke !== active.stroke); release(); changed(); paint();
    status.textContent = 'Drawing was interrupted. Check the signature or draw it again.';
  }
  function reset() {
    release(); strokes = []; image = null; revision++;
    paint(); status.textContent = '';
  }
  function enoughInk() {
    return strokes.some(stroke => stroke.length > 1 && stroke.reduce((distance,p,index) => index ? distance + Math.hypot(p.x-stroke[index-1].x,p.y-stroke[index-1].y) : 0,0) >= 12);
  }
  async function getEvidence() {
    if (disposed) throw new Error('This signing view is closed.');
    if (mode === 'paper_scan') return {file:fileInput.files?.[0], method:mode};
    if (active || !enoughInk()) throw new Error('Draw your signature in the box before saving.');
    const generation = revision;
    if (!image) {
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      if (disposed || generation !== revision) throw new Error('Signature changed before saving. Check it and try again.');
      if (!blob || blob.type !== 'image/png') throw new Error('Signature could not be prepared. Try again or upload a signed paper copy.');
      image = blob;
    }
    return {file:image, method:mode};
  }
  function setDisabled(value) {
    disabled = value;
    for (const button of [screen,paper,clearButton]) button.disabled = value;
    canvas.setAttribute('aria-disabled', String(value));
  }
  function dispose() {
    if (disposed) return;
    disposed = true; reset();
    for (const remove of removers) remove();
    // Resetting bitmap dimensions erases pixel data, including detached canvases.
    canvas.width = 960; context = null; root.innerHTML = '';
  }
  listen(screen,'click',()=>select('screen_signature'));
  listen(paper,'click',()=>select('paper_scan'));
  listen(clearButton,'click',()=>{if(!disposed && !disabled){reset();changed();status.textContent='Signature cleared. The applicant can sign again.';}});
  listen(canvas,'pointerdown',down); listen(canvas,'pointermove',move);
  listen(canvas,'pointerup',end); listen(canvas,'pointercancel',cancel); listen(canvas,'lostpointercapture',cancel);
  return {getEvidence,setDisabled,reset,dispose,isDirty:()=>!disposed && strokes.some(stroke=>stroke.length),getMethod:()=>mode};
}

export function signatureAttestation(method) {
  return method === 'screen_signature'
    ? {capture_method:method,witnessed_screen_signature:'true'}
    : {witnessed_wet_signature:'true'};
}
