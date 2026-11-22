---
title: "API Rate Limits and Best Practices"
category: "api_failure"
tags: ["api", "rate-limit", "429", "throttling", "best-practices", "exponential-backoff"]
summary: "Understanding CloudDesk API rate limits, how to handle 429 errors, and best practices for high-volume integrations."
---

# API Rate Limits and Best Practices

## Rate Limit Tiers

CloudDesk enforces two types of rate limits to ensure fair usage:

| Plan | Requests per Minute (burst) | Requests per Day |
|---|---|---|
| Free | 60 | 1,000 |
| Pro | 600 | 50,000 |
| Business | 2,000 | 250,000 |
| Enterprise | 10,000 | Unlimited |

## Burst vs. Daily Limits

- **Burst limit**: The maximum number of requests allowed in a 60-second rolling window. Exceeding this returns a `429 Too Many Requests` response.
- **Daily limit**: The total requests allowed in a 24-hour UTC day. Free and Pro plans have daily caps; Business and Enterprise do not.

## Understanding 429 Responses

When you exceed a rate limit, the API returns:

```json
{
  "error": "rate_limit_exceeded",
  "retry_after": 30
}
```

The `retry_after` field (in seconds) tells you the minimum wait time before retrying.

## Best Practices

### 1. Implement Exponential Backoff

Do not retry immediately after a 429. Use exponential backoff:

```python
import time, random

def call_with_retry(func, max_retries=5):
    for attempt in range(max_retries):
        response = func()
        if response.status_code != 429:
            return response
        wait = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(wait)
    raise Exception("Max retries exceeded")
```

### 2. Respect the Retry-After Header

Always read the `retry_after` value and wait at least that long before the next request.

### 3. Batch Operations

Where possible, use batch API endpoints to reduce the number of requests. For example, `POST /api/v1/files/batch` can upload multiple files in one request.

### 4. Distribute Load

Avoid running all API calls at the same second (e.g., the top of the hour). Add jitter to scheduled jobs.

### 5. Monitor Your Usage

Your current API usage is visible at **Settings → API → Usage Dashboard**. Set up usage alerts before you approach your daily limit.

## Nightly Sync Jobs

If you run nightly sync jobs, ensure:
1. The job is not issuing more than 600 requests per minute (Pro) or 2,000 (Business).
2. The job is spread over the full available window, not front-loaded.
3. Errors are caught and retried with backoff, not failed silently.

## Service-Level Incidents

Occasionally, CloudDesk infrastructure changes may temporarily affect rate-limiting behavior even when you are within your quota. Check the **Status Page** (`status.clouddesk.example`) for active incidents before filing a support ticket.
