/**
 * tests/test_company_stale_id_recovery.test.js — PR #962
 *
 * Verifies the CompanyScreen self-heals when the localStorage company ID
 * is stale (404 from backend) instead of showing a permanent error.
 *
 * Source-inspection test — reads CompanyScreen.jsx as text + verifies
 * the 404 recovery logic exists.
 */
const { describe, test, expect } = require('@jest/globals');

const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(
  path.join(__dirname, '..', 'v5', 'screens', 'CompanyScreen.jsx'),
  'utf-8'
);

describe('Company stale ID recovery (PR #962)', () => {
  test('404 handler clears localStorage COMPANY_ID_KEY', () => {
    // When getCompany returns 404, the stale ID must be removed from localStorage
    expect(src).toMatch(/response\?\.status === 404/);
    expect(src).toMatch(/localStorage\.removeItem\(COMPANY_ID_KEY\)/);
  });

  test('404 handler auto-selects first available company', () => {
    // After clearing the stale ID, the code should try listCompanies + select list[0]
    expect(src).toMatch(/listData\.companies/);
    expect(src).toMatch(/setSelectedCompanyId\(list\[0\]\.id\)/);
  });

  test('list-loader validates storedId against the list', () => {
    // The mount list-loader must check if storedId is in the list before using it
    expect(src).toMatch(/list\.find\(c => c\.id === storedId\)/);
    // If storedId is not in the list, it should be cleared
    expect(src).toMatch(/localStorage\.removeItem\(COMPANY_ID_KEY\)/);
  });
});
