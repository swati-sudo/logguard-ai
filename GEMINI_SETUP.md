# Google Gemini Setup Guide

This document explains how to set up Google Gemini API for LogGuard AI, replacing the previous OpenAI integration.

## Overview

LogGuard AI now uses **Google Gemini API** for all LLM tasks:
- PII redaction (context-aware)
- Code fixing and remediation
- Root cause analysis
- Edge case PII detection

## Setup Options

### Option A: Quick Setup (API Key Only)

**Best for:** Development, testing, quick prototyping

#### 1. Get a Gemini API Key
```bash
# Visit: https://aistudio.google.com/app/apikey
# Click "Create API Key"
# Copy the key
```

#### 2. Update `.env`
```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-pro
ENABLE_LLM_DETECTION=true
```

#### 3. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

#### 4. Run the app
```bash
bash start.sh
```

---

### Option B: Production Setup (Service Account)

**Best for:** Production, enterprise, better security & audit trails

#### 1. Create Google Cloud Project
```bash
# Visit: https://console.cloud.google.com/
# Create a new project
# Note the Project ID
```

#### 2. Enable Gemini API
```bash
# In Google Cloud Console:
# - Navigate to "APIs & Services" > "Library"
# - Search for "Generative Language API"
# - Click "Enable"
```

#### 3. Create Service Account
```bash
# In Google Cloud Console:
# - Go to "APIs & Services" > "Credentials"
# - Click "Create Credentials" > "Service Account"
# - Name: "logguard-ai"
# - Grant roles: "Editor" (or minimum required)
# - Click "Create"
```

#### 4. Create and Download Service Account Key
```bash
# In the Service Account details:
# - Go to "Keys" tab
# - Click "Add Key" > "Create new key"
# - Choose "JSON"
# - Download and save as `/path/to/service-account-key.json`
```

#### 5. Get Gemini API Key
```bash
# You still need an API key for Gemini API access
# Visit: https://aistudio.google.com/app/apikey
# Create an API key
```

#### 6. Update `.env`
```env
GOOGLE_SERVICE_ACCOUNT_JSON=/absolute/path/to/service-account-key.json
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-pro
ENABLE_LLM_DETECTION=true
```

#### 7. Verify Setup
```bash
# Check that the service account JSON file exists
ls -la /absolute/path/to/service-account-key.json

# Install dependencies
cd backend
pip install -r requirements.txt

# Run the app
bash start.sh
```

---

## Gemini Models Available

| Model | Capabilities | Speed | Cost |
|-------|--------------|-------|------|
| `gemini-1.5-pro` | Advanced reasoning, long context | Medium | $ |
| `gemini-1.5-flash` | Fast, good for real-time | Fast | $ |
| `gemini-pro` | General purpose | Medium | $ |
| `gemini-pro-vision` | Vision + text (if enabled) | Medium | $$$ |

**Recommended:** `gemini-1.5-pro` (good balance of capability and cost)

To use a different model, update `.env`:
```env
GEMINI_MODEL=gemini-1.5-flash
```

---

## Troubleshooting

### "Failed to initialize Gemini client"
**Solution:** Check that:
1. `GEMINI_API_KEY` is set correctly
2. Service account JSON path is absolute (not relative)
3. File permissions: `chmod 644 /path/to/service-account-key.json`

### "Permission denied" error
**Solution:** The service account needs these permissions:
- `aiplatform.models.list`
- `aiplatform.models.get`
- Or simpler: Grant "Editor" role temporarily

### API rate limits exceeded
**Solution:**
1. Check Google Cloud quotas
2. Request quota increase in Google Cloud Console
3. Consider upgrading to a paid plan

### "API not enabled"
**Solution:**
1. Go to Google Cloud Console
2. Search for "Generative Language API"
3. Click "Enable"

---

## Feature Flags

Control which LLM features are enabled:

```env
# Phase 3 PII detection using Gemini (slow but catches edge cases)
ENABLE_LLM_DETECTION=true

# Semantic log clustering using sentence-transformers
ENABLE_SEMANTIC_ANOMALY=true

# Check credentials against breach databases
ENABLE_BREACH_CHECK=false

# Create actual GitHub PRs (requires GITHUB_TOKEN)
ENABLE_GITHUB_INTEGRATION=false
```

---

## Cost Estimation

**Gemini 1.5 Pro Pricing:**
- Input: $1.25 / 1M tokens
- Output: $5 / 1M tokens

**Per-operation costs (estimated):**
- PII Redaction: ~0.001¢ (short text)
- Code Fixing: ~0.01¢ (medium code)
- Root Cause Analysis: ~0.02¢ (multi-log analysis)

**For 10,000 logs/day:**
- ~$1-2/day with LLM detection enabled
- ~$0.10/day without LLM detection (regex only)

---

## Switching Back to OpenAI (Optional)

If you want to switch back to OpenAI:

### 1. Update requirements.txt
```
# Remove these:
google-generativeai==0.3.0
google-auth==2.27.0
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0

# Add back:
openai==1.52.0
```

### 2. Update `.env`
```env
OPENAI_API_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxx
OPENAI_MODEL=gpt-4-turbo
```

### 3. Revert agent files
```bash
# The agent files were converted to Gemini
# You'd need to replace the imports and API calls back to OpenAI
# Consider using git to revert: git checkout HEAD -- backend/agents/
```

---

## API Reference

### Privacy Agent (LLM-based redaction)
```python
# Endpoint: POST /api/analyze/code
# Request:
{
  "code": "logger.info('User login: iban=' + user.getIban() + ', password=' + password);"
}

# Response:
{
  "redacted": "logger.info('User login: iban=[REDACTED_IBAN]');",
  "findings": [...]
}
```

### Remediation Agent (Code fixing)
```python
# Endpoint: Internal (used by pipeline)
# Generates fix using Gemini and creates GitHub PR if enabled
```

### Root Cause Analysis
```python
# Endpoint: GET /api/analytics/root-cause
# Response:
{
  "root_cause": "Database connection timeout during peak traffic",
  "severity": "HIGH",
  "action": "Scale database connections or optimize query"
}
```

---

## Security Best Practices

1. **Never commit `.env` to git:**
   ```bash
   # Add to .gitignore
   backend/.env
   backend/.env.local
   *.json  # Service account keys
   ```

2. **Rotate API keys regularly:**
   - Delete old key in Google AI Studio
   - Generate new key
   - Update in `.env`

3. **Restrict service account permissions:**
   - Grant minimal required roles
   - Use resource-level IAM policies
   - Enable audit logging

4. **Use absolute paths for service account JSON:**
   ```env
   # ✅ Good
   GOOGLE_SERVICE_ACCOUNT_JSON=/Users/username/secrets/service-account-key.json
   
   # ❌ Bad (security risk)
   GOOGLE_SERVICE_ACCOUNT_JSON=./backend/service-account-key.json
   ```

---

## Support

- **Google Gemini Docs:** https://ai.google.dev/
- **API Reference:** https://ai.google.dev/tutorials/python_quickstart
- **Pricing:** https://ai.google.dev/pricing
- **Issues:** Open a GitHub issue on this repo

