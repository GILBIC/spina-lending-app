import assert from 'node:assert/strict';

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
