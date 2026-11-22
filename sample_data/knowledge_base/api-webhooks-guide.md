---
title: "Webhooks and Event Notifications"
category: "api_failure"
tags: ["webhooks", "events", "api", "automation", "notifications", "integration"]
summary: "How to configure CloudDesk webhooks to receive real-time event notifications in your own systems."
---

# Webhooks and Event Notifications

## What Are Webhooks?

Webhooks let CloudDesk push real-time event notifications to your server or integration platform (Zapier, Make, etc.) whenever something happens in your workspace — a file is uploaded, a comment is added, or a member joins.

This is more efficient than polling the API, as you receive updates instantly without issuing repeated requests.

## Supported Events

| Event | Description |
|---|---|
| `file.uploaded` | A new file was uploaded |
| `file.deleted` | A file was deleted |
| `file.shared` | A file was shared (internally or externally) |
| `comment.created` | A comment was added to a file |
| `member.added` | A new member was invited to the workspace |
| `member.removed` | A member was removed from the workspace |
| `workspace.storage.warning` | Storage usage exceeds 80% of quota |
| `workspace.storage.full` | Storage quota exceeded |

## Setting Up a Webhook

1. Go to **Settings → API → Webhooks**.
2. Click **Add Webhook**.
3. Enter the **Endpoint URL** where CloudDesk will send POST requests.
4. Select the events you want to receive.
5. Click **Save**.

CloudDesk will immediately send a **verification request** to your endpoint. Respond with the `challenge` value to confirm ownership.

## Webhook Payload Format

Each event is sent as a POST request with a JSON body:

```json
{
  "event": "file.uploaded",
  "timestamp": "2024-01-15T10:30:00Z",
  "workspace": "my-workspace",
  "data": {
    "file_id": "file-abc-123",
    "name": "quarterly-report.pdf",
    "size": 102400,
    "uploaded_by": "user@example.com"
  }
}
```

## Verifying Webhook Signatures

Each request includes an `X-CloudDesk-Signature` header containing an HMAC-SHA256 signature of the request body using your webhook signing secret.

Verify this in your handler to ensure the request is from CloudDesk and not spoofed:

```python
import hmac, hashlib

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

## Retry Policy

If your endpoint returns a non-2xx status or times out (> 10 seconds), CloudDesk retries the event:
- Retry 1: after 1 minute
- Retry 2: after 5 minutes
- Retry 3: after 30 minutes
- Retry 4: after 2 hours

After 4 retries, the event is marked as failed and logged in **Settings → API → Webhook Logs**.

## Webhook Logs

Review all recent deliveries under **Settings → API → Webhook Logs**. Each entry shows the event, timestamp, HTTP status returned, and response body. You can manually re-deliver failed events from this page.
