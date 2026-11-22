---
title: "API Authentication and Key Management"
category: "api_failure"
tags: ["api", "authentication", "api-key", "oauth", "bearer-token", "file-upload"]
summary: "How to authenticate with the CloudDesk API, manage API keys, and use the file upload endpoint."
---

# API Authentication and Key Management

## API Key vs. OAuth Token

CloudDesk supports two authentication methods:

| Method | Use case |
|---|---|
| **API Key** | Server-to-server integrations, scripts, automation |
| **OAuth 2.0** | Applications that act on behalf of a user |

For most integrations (nightly sync jobs, CLI tools), an API key is the right choice.

## Creating an API Key

1. Go to **Settings → API → API Keys**.
2. Click **Create New Key**.
3. Give the key a descriptive name (e.g., "nightly-sync-prod").
4. Select the **permissions** the key needs (read-only vs. read-write).
5. Click **Create**. **Copy the key immediately** — it is only shown once.

Store API keys securely (e.g., in a secrets manager, not in source code).

## Using an API Key

Pass the API key as a Bearer token in the `Authorization` header:

```
Authorization: Bearer cd_live_sk_xxxxxxxxxxxxxxxxxxxx
```

## File Upload Endpoint

To upload a file via the API:

```
POST /api/v1/workspaces/{workspace_slug}/files
Content-Type: multipart/form-data
Authorization: Bearer cd_live_sk_xxxx

Form fields:
  file       — the file binary
  folder_id  — (optional) target folder ID
  name       — (optional) override filename
```

**Example with curl:**

```bash
curl -X POST https://api.clouddesk.example/api/v1/workspaces/my-workspace/files \
  -H "Authorization: Bearer cd_live_sk_xxxx" \
  -F "file=@/path/to/document.pdf" \
  -F "folder_id=folder-abc-123"
```

**Response:**

```json
{
  "id": "file-abc-123",
  "name": "document.pdf",
  "size": 102400,
  "url": "https://cdn.clouddesk.example/files/file-abc-123",
  "created_at": "2024-01-15T10:30:00Z"
}
```

## Batch File Upload

To upload multiple files in a single request (more efficient, uses one API call):

```
POST /api/v1/workspaces/{workspace_slug}/files/batch
Content-Type: multipart/form-data

Form fields:
  files[]    — multiple file binaries (up to 10 per request)
  folder_id  — (optional) target folder for all files
```

## API Documentation

Full API documentation is available at **Settings → API → Documentation** or at `https://api.clouddesk.example/docs`. The interactive Swagger UI allows you to test endpoints directly.

## Revoking API Keys

Revoke a key immediately if it is compromised:
1. Go to **Settings → API → API Keys**.
2. Click **Revoke** next to the key.
3. The key becomes invalid immediately.
