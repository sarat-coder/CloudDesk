---
title: "Slack Integration Setup and Troubleshooting"
category: "integration"
tags: ["slack", "integration", "notifications", "webhook", "automation"]
summary: "How to set up and troubleshoot the CloudDesk-Slack integration for notifications and workflow alerts."
---

# Slack Integration Setup and Troubleshooting

## What the Slack Integration Does

The CloudDesk-Slack integration sends notifications to a Slack channel when:
- A new file is uploaded
- A comment is added to a file
- A file is shared externally
- A workflow approval is required (for agents)
- An escalation is created

## Setup

1. In CloudDesk, go to **Settings → Integrations → Slack**.
2. Click **Connect to Slack** and authorize the CloudDesk app in Slack.
3. Select the Slack channel where notifications should be posted.
4. Choose which event types you want to receive.
5. Click **Save**.

A test message is sent to your chosen channel to confirm the connection.

## Why Notifications Stopped

The most common reasons the integration stops posting:

### 1. Slack Bot Token Revoked

If a Slack workspace admin revoked CloudDesk's bot token (for example, during an app audit), the integration loses permission to post.

**Fix:**
1. In CloudDesk, go to **Settings → Integrations → Slack** and click **Disconnect**.
2. Click **Connect to Slack** again and re-authorize.
3. A new test message will confirm the connection.

### 2. Slack Channel Archived or Deleted

If the target Slack channel was archived or deleted, messages cannot be posted to it.

**Fix:** Select a new channel in **Settings → Integrations → Slack → Edit Channel**.

### 3. CloudDesk App Removed from Slack Workspace

If the CloudDesk app was removed from your Slack workspace entirely:
1. A Slack workspace admin must reinstall the app: go to Slack's App Directory and search for CloudDesk.
2. After reinstallation, reconnect in CloudDesk settings.

### 4. Webhook Signing Secret Changed

For customers using the advanced webhook mode (instead of the standard OAuth integration), if the webhook signing secret is rotated in CloudDesk but not updated in Slack, notifications fail silently.

**Fix:** Copy the new signing secret from **Settings → Integrations → Webhooks** and update it in your Slack app configuration.

## Testing the Integration

After reconnecting, click **Send Test Message** in **Settings → Integrations → Slack** to verify the connection. If the test message does not arrive within 60 seconds, check the channel name is correct and that the CloudDesk app has permission to post there.

## Notification Filtering

To reduce noise, you can filter notifications by:
- Event type (uploads only, comments only, etc.)
- Workspace (post from workspace A only)
- File type (documents only, etc.)
