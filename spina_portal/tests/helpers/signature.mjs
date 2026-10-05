import assert from 'node:assert/strict';
import { fire } from './dom.mjs';

export function prepareSignature(root, {deferExport = false} = {}) {
  const canvas = root.querySelector('[data-signature-canvas]');
  assert.ok(canvas, 'The signing workflow must contain an on-screen signature pad');
  let exports = 0, finish, clears = 0;
  canvas.getBoundingClientRect = () => ({left:0,top:0,width:640,height:240});
  canvas.getContext = () => ({fillRect(){clears++;},clearRect(){clears++;},beginPath(){},moveTo(){},lineTo(){},stroke(){}});
  canvas.setPointerCapture = () => {};
  canvas.releasePointerCapture = () => {};
  const file = new Blob(['synthetic PNG signature'], {type:'image/png'});
  canvas.toBlob = callback => { exports++; finish=()=>callback(file); if(!deferExport)finish(); };
  fire(root.querySelector('[data-signature-screen]'),'click');
  const point = (type,x,y,id=1) => {
    const event = new Event(type,{cancelable:true});
    Object.assign(event,{clientX:x,clientY:y,pointerId:id,button:0,isPrimary:true});
    canvas.dispatchEvent(event);
  };
  return {canvas,file,point,draw(){point('pointerdown',40,130);point('pointermove',100,60);point('pointermove',200,170);point('pointerup',330,70);},finish:()=>finish(),get exports(){return exports;},get clears(){return clears;}};
}
