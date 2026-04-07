#!/usr/bin/env node
/**
 * Test Google Gemini API Key
 * Verifies the free-tier connection works
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

const testPrompt = {
  contents: [{
    parts: [{
      text: "Say 'Quota ledger test successful' in exactly 5 words."
    }]
  }]
};

const options = {
  hostname: 'generativelanguage.googleapis.com',
  path: `/v1beta/models/gemini-2.5-flash:generateContent?key=${API_KEY}`,
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  }
};

console.log('Testing Google Gemini API...');
console.log(`Model: gemini-2.5-flash`);
console.log(`Prompt: "${testPrompt.contents[0].parts[0].text}"\n`);

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
      const text = response.candidates[0].content.parts[0].text;
      const tokens = response.usageMetadata.totalTokenCount;

      console.log('✅ API Test Successful!');
      console.log(`Response: "${text}"`);
      console.log(`Tokens used: ${tokens}`);
      console.log(`Cost: $0 (free tier)`);
      console.log('\n🔥 Free-tier max burn ready to go!');
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

req.write(JSON.stringify(testPrompt));
req.end();
