#!/usr/bin/env node
/**
 * List available Google Gemini models
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// Load API key from .env.quota
const envPath = path.join(__dirname, '..', '.env.quota');
const envContent = fs.readFileSync(envPath, 'utf8');
const apiKeyMatch = envContent.match(/GOOGLE_API_KEY=(.+)/);
if (!apiKeyMatch) {
  console.error('❌ GOOGLE_API_KEY not found in .env.quota');
  process.exit(1);
}
const API_KEY = apiKeyMatch[1].trim();

const options = {
  hostname: 'generativelanguage.googleapis.com',
  path: `/v1beta/models?key=${API_KEY}`,
  method: 'GET'
};

console.log('Fetching available Gemini models...\n');

const req = https.request(options, (res) => {
  let data = '';
  
  res.on('data', (chunk) => {
    data += chunk;
  });
  
  res.on('end', () => {
    if (res.statusCode !== 200) {
      console.error(`❌ API Error (${res.statusCode})`);
      console.error(data);
      process.exit(1);
    }

    try {
      const response = JSON.parse(data);
      console.log('Available models:');
      response.models.forEach(model => {
        if (model.supportedGenerationMethods.includes('generateContent')) {
          console.log(`  - ${model.name} (${model.displayName})`);
        }
      });
    } catch (err) {
      console.error('❌ Failed to parse response');
      console.error(err.message);
      process.exit(1);
    }
  });
});

req.on('error', (err) => {
  console.error('❌ Request failed');
  console.error(err.message);
  process.exit(1);
});

req.end();
