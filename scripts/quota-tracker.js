#!/usr/bin/env node
/**
 * Quota Tracker — Free-Tier-First Usage Logger
 * Logs every LLM call to quota_ledger.json
 * Enforces free-tier-first routing policy
 */

const fs = require('fs');
const path = require('path');

const LEDGER_PATH = path.join(__dirname, '..', 'quota_ledger.json');
const AUDIT_PATH = path.join(__dirname, '..', 'paperclip_audit.jsonl');

class QuotaTracker {
  constructor() {
    this.ledger = this.loadLedger();
  }

  loadLedger() {
    if (!fs.existsSync(LEDGER_PATH)) {
      throw new Error('quota_ledger.json not found');
    }
    return JSON.parse(fs.readFileSync(LEDGER_PATH, 'utf8'));
  }

  saveLedger() {
    fs.writeFileSync(LEDGER_PATH, JSON.stringify(this.ledger, null, 2));
  }

  /**
   * Log a model call
   * @param {string} service - Service name (google_gemini, groq, openai, etc)
   * @param {string} model - Model name
   * @param {number} tokens - Token count
   * @param {number} cost - Cost in USD (0 for free tier)
   * @param {string} purpose - What was this call for?
   */
  logCall(service, model, tokens, cost, purpose) {
    const timestamp = new Date().toISOString();
    
    // Update service usage
    if (this.ledger.free_tiers[service]) {
      this.ledger.free_tiers[service].current_usage.requests_today += 1;
      this.ledger.free_tiers[service].current_usage.tokens_today += tokens;
    } else if (this.ledger.paid_tiers[service]) {
      this.ledger.paid_tiers[service].current_usage.cost_today += cost;
      this.ledger.paid_tiers[service].current_usage.cost_this_month += cost;
    }

    // Update monthly budget
    this.ledger.monthly_budget.current_spend += cost;
    this.ledger.last_updated = timestamp;

    // Append to audit log (in-memory, limited to last 100)
    this.ledger.audit_log.push({
      timestamp,
      service,
      model,
      tokens,
      cost,
      purpose
    });
    if (this.ledger.audit_log.length > 100) {
      this.ledger.audit_log.shift();
    }

    // Append to paperclip audit (append-only file)
    const auditEntry = {
      timestamp,
      type: 'llm_call',
      service,
      model,
      tokens,
      cost,
      purpose
    };
    fs.appendFileSync(AUDIT_PATH, JSON.stringify(auditEntry) + '\n');

    this.saveLedger();
  }

  /**
   * Check if we're approaching free-tier limits
   * @param {string} service - Service name
   * @returns {object} Status and warnings
   */
  checkLimits(service) {
    const tier = this.ledger.free_tiers[service];
    if (!tier) return { ok: true };

    const usage = tier.current_usage;
    const limits = tier.limits;

    const warnings = [];
    if (limits.requests_per_day) {
      const pct = (usage.requests_today / limits.requests_per_day) * 100;
      if (pct > 80) warnings.push(`Requests: ${pct.toFixed(1)}% of daily limit`);
    }
    if (limits.tokens_per_day) {
      const pct = (usage.tokens_today / limits.tokens_per_day) * 100;
      if (pct > 80) warnings.push(`Tokens: ${pct.toFixed(1)}% of daily limit`);
    }

    return {
      ok: warnings.length === 0,
      warnings
    };
  }

  /**
   * Get next available free-tier service for a task type
   * @param {string} taskType - monitoring, parsing, planning, etc
   * @returns {string|null} Service name or null if all exhausted
   */
  getNextFreeTier(taskType) {
    const rule = this.ledger.routing_rules[taskType];
    if (!rule) return null;

    for (const service of rule.preferred) {
      const tier = this.ledger.free_tiers[service];
      if (!tier) continue;
      if (tier.status !== 'ready' && tier.status !== 'active') continue;

      const check = this.checkLimits(service);
      if (check.ok) return service;
    }

    return null; // All free tiers exhausted
  }

  /**
   * Report current quota status
   */
  reportStatus() {
    console.log('=== Quota Ledger Status ===');
    console.log(`Monthly Budget: $${this.ledger.monthly_budget.current_spend.toFixed(2)} / $${this.ledger.monthly_budget.hard_limit_usd}`);
    
    console.log('\nFree Tiers:');
    for (const [key, tier] of Object.entries(this.ledger.free_tiers)) {
      if (tier.status === 'ready' || tier.status === 'active') {
        console.log(`  ${tier.service}:`);
        console.log(`    Requests today: ${tier.current_usage.requests_today}`);
        if (tier.current_usage.tokens_today) {
          console.log(`    Tokens today: ${tier.current_usage.tokens_today}`);
        }
        const check = this.checkLimits(key);
        if (!check.ok) {
          console.log(`    ⚠️  ${check.warnings.join(', ')}`);
        }
      }
    }

    console.log('\nPaid Tiers:');
    for (const [key, tier] of Object.entries(this.ledger.paid_tiers)) {
      console.log(`  ${tier.service}: $${tier.current_usage.cost_this_month.toFixed(2)} this month`);
    }
  }
}

// CLI
if (require.main === module) {
  const tracker = new QuotaTracker();
  const args = process.argv.slice(2);
  const command = args[0];

  if (command === 'log') {
    const [, service, model, tokens, cost, ...purposeParts] = args;
    const purpose = purposeParts.join(' ');
    tracker.logCall(service, model, parseInt(tokens), parseFloat(cost), purpose);
    console.log('✓ Logged to quota ledger');
  } else if (command === 'status') {
    tracker.reportStatus();
  } else if (command === 'check') {
    const [, service] = args;
    const check = tracker.checkLimits(service);
    console.log(JSON.stringify(check, null, 2));
  } else if (command === 'next') {
    const [, taskType] = args;
    const service = tracker.getNextFreeTier(taskType);
    console.log(service || 'EXHAUSTED');
  } else {
    console.log('Usage:');
    console.log('  quota-tracker.js log <service> <model> <tokens> <cost> <purpose>');
    console.log('  quota-tracker.js status');
    console.log('  quota-tracker.js check <service>');
    console.log('  quota-tracker.js next <taskType>');
  }
}

module.exports = QuotaTracker;
