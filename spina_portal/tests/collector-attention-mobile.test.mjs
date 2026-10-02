import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {collectorAttentionMarkup} from '../assets/collector-route-view.js';
test('Collector attention uses existing phone card pattern with labeled cells and scoped form layout',async()=>{const css=await readFile(new URL('../assets/app.css',import.meta.url),'utf8');const html=collectorAttentionMarkup([{route_entry_id:'r',client_name:'Very long borrower',area:'Area',loan_id:'l',loan_type:'Regular',contract_today_unpaid_amount:'100.00'}]);assert.match(html,/mobile-card-table/);assert.match(css,/#collector-route \.collector-entry-summary/);assert.match(css,/#collector-route \.collector-entry-form/);assert.match(css,/\.collector-route-filters/);});
