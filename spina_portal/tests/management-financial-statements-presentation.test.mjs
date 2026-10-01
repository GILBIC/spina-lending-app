import assert from 'node:assert/strict';
import test from 'node:test';

import { financialStatementsMarkup } from '../assets/management-financial-statements.js';

function emptyStatements(status='open') {
  return {
    statements:{
      period:{label:'August 2026',start_date:'2026-08-01',end_date:'2026-08-31',status},
      profit_or_loss:{
        income_lines:[],expense_lines:[],total_income:'0.00',total_expenses:'0.00',net_income:'0.00',
      },
      financial_position:{
        as_of_date:'2026-08-31',asset_lines:[],liability_lines:[],equity_lines:[],
        total_assets:'0.00',total_liabilities:'0.00',recorded_equity:'0.00',
        unclosed_earnings_to_date:'0.00',total_equity:'0.00',total_liabilities_and_equity:'0.00',
        balanced:true,
      },
      source:'posted_general_ledger_only',
      notice:'These statements are generated only from posted General Ledger entries. Draft journals are excluded. Opening-balance cutover, automatic lending posting, ECL posting, tax posting, and formal closing entries remain separate controlled accounting stages.',
    },
  };
}

test('empty Financial Statements use one compact no-posted-lines state', () => {
  const markup=financialStatementsMarkup(emptyStatements());
  assert.match(markup,/data-financial-statements-empty/);
  assert.match(markup,/No posted General Ledger activity for this period yet/i);
  assert.equal((markup.match(/No posted General Ledger line is available/g)||[]).length,0);
  assert.doesNotMatch(markup,/<table/);
  assert.match(markup,/Total income/);
  assert.match(markup,/Total assets/);
  assert.match(markup,/₱0\.00/);
});

test('Financial Statements translate source and open-period status for Management', () => {
  const markup=financialStatementsMarkup(emptyStatements('open'));
  assert.match(markup,/Posted General Ledger only/);
  assert.doesNotMatch(markup,/posted_general_ledger_only/);
  assert.match(markup,/Open period/i);
  assert.match(markup,/provisional/i);
  assert.match(markup,/Balanced/i);
  assert.match(markup,/no posted lines/i);
});

test('Financial Statements keep technical lifecycle notice under About these statements', () => {
  const markup=financialStatementsMarkup(emptyStatements());
  assert.match(markup,/<details[^>]*data-financial-statements-about/);
  assert.match(markup,/>About these statements</);
  assert.match(markup,/opening-balance cutover/i);
  assert.match(markup,/ECL posting/i);
});

test('Financial Statements use clearer current-period earnings wording', () => {
  const payload=emptyStatements('closed');
  payload.statements.financial_position.unclosed_earnings_to_date='333.00';
  payload.statements.financial_position.asset_lines=[{account_code:'1100',account_name:'Cash',amount:'500.00'}];
  payload.statements.financial_position.liability_lines=[{account_code:'2100',account_name:'Payables',amount:'200.00'}];
  payload.statements.financial_position.equity_lines=[{account_code:'3100',account_name:'Capital',amount:'300.00'}];
  const markup=financialStatementsMarkup(payload);
  assert.match(markup,/Current-period earnings \(not yet closed\)/);
  assert.doesNotMatch(markup,/Unclosed earnings to date/);
  assert.match(markup,/Cash/);
  assert.match(markup,/Payables/);
  assert.match(markup,/Capital/);
});
