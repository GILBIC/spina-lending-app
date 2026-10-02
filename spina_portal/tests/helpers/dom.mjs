import assert from 'node:assert/strict';
const fixtureDocument = new EventTarget();
fixtureDocument.createElement = tag => new Element(tag);

// Event-capable DOM fixture with parsed children and live innerHTML. Detached
// elements retain their listeners so integration tests can verify disposal.
export class Element extends EventTarget {
  constructor(tag = 'div', attributes = {}) {
    super();
    this.tag = tag;
    this.attributes = attributes;
    this.children = [];
    this.value = attributes.value || '';
    this.disabled = Object.hasOwn(attributes, 'disabled');
    this.hidden = Object.hasOwn(attributes, 'hidden');
    this.parentElement = null;
    this.ownerDocument = fixtureDocument;
  }

  get innerHTML() {
    return this.children.map((child) => typeof child === 'string' ? child : child.outerHTML).join('');
  }

  set innerHTML(markup) {
    this.children = [];
    const stack = [this];
    for (const token of String(markup).matchAll(/<\/?[a-z][^>]*>|[^<]+/gi)) {
      const text = token[0];
      if (text.startsWith('</')) {
        stack.pop();
      } else if (text.startsWith('<')) {
        const [, tag, rawAttributes] = text.match(/^<([a-z][\w-]*)([^>]*)>/i);
        const attributes = {};
        for (const attribute of rawAttributes.matchAll(/([^\s=/>]+)(?:="([^"]*)")?/g)) {
          attributes[attribute[1]] = attribute[2] ?? '';
        }
        const element = new Element(tag, attributes);
        element.parentElement = stack.at(-1);
        element.ownerDocument = this.ownerDocument;
        stack.at(-1).children.push(element);
        if (!['input', 'br', 'hr', 'img'].includes(tag)) stack.push(element);
      } else stack.at(-1).children.push(text);
    }
  }

  get outerHTML() {
    const attributes = Object.entries(this.attributes).map(([key, value]) => ` ${key}="${value}"`).join('');
    return `<${this.tag}${attributes}>${this.innerHTML}${['input', 'br', 'hr', 'img'].includes(this.tag) ? '' : `</${this.tag}>`}`;
  }

  get textContent() {
    return this.innerHTML.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
  }

  set textContent(value) {
    this.children = [String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')];
  }

  getAttribute(name) { return this.attributes[name] ?? null; }
  setAttribute(name, value) { this.attributes[name] = String(value); }
  removeAttribute(name) { delete this.attributes[name]; }
  focus() { this.focused = true; }
  get className() {return this.attributes.class || '';}
  set className(value) {this.attributes.class=String(value);}
  get isConnected() {return this._isConnected ?? (this.parentElement ? this.parentElement.isConnected : true);}
  set isConnected(value) {this._isConnected=value;}
  get dataset() {return this._dataset || Object.fromEntries(Object.entries(this.attributes).filter(([key])=>key.startsWith('data-')).map(([key,value])=>[key.slice(5).replace(/-([a-z])/g,(_,letter)=>letter.toUpperCase()),value]));}
  set dataset(value) {this._dataset=value;}
  appendChild(child) {child.remove();this.children.push(child);child.parentElement=this;child.ownerDocument=this.ownerDocument;return child;}
  remove() {if(this.parentElement)this.parentElement.children=this.parentElement.children.filter(child=>child!==this);this.parentElement=null;}
  replaceWith(child) {const parent=this.parentElement;if(!parent)return;const index=parent.children.indexOf(this);child.remove();parent.children[index]=child;child.parentElement=parent;child.ownerDocument=parent.ownerDocument;this.parentElement=null;}
  closest(selector) {let node=this;while(node){if(selector==='label' && node.tag==='label')return node;if(selector==='[hidden]' && node.hidden)return node;if(selector==='[inert]' && node.getAttribute('inert')!==null)return node;node=node.parentElement;}return null;}
  reset() {for(const input of this.querySelectorAll('input')){input.value=input.getAttribute('value') || '';input.checked=false;}for(const input of this.querySelectorAll('textarea'))input.value='';}

  querySelectorAll(selector) {
    const match = selector.match(/^([\w-]+)?(?:#([\w-]+)|\.([\w-]+))?(?:\[([\w-]+)(?:="([^"]*)")?\])?$/);
    assert.ok(match, `DOM fixture needs a supported selector: ${selector}`);
    const [, tag, id, className, attribute, value] = match;
    const found = [];
    for (const child of this.children) {
      if (typeof child === 'string') continue;
      if ((!tag || child.tag === tag)
        && (!id || child.attributes.id === id)
        && (!className || (child.attributes.class || '').split(/\s+/).includes(className))
        && (!attribute || Object.hasOwn(child.attributes, attribute))
        && (value === undefined || child.attributes[attribute] === value)) found.push(child);
      found.push(...child.querySelectorAll(selector));
    }
    return found;
  }

  querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
}

export function fire(element, type) {
  const event = new Event(type, { cancelable: true });
  element.dispatchEvent(event);
  return event;
}
