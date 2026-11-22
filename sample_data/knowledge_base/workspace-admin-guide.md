---
title: "Workspace Administration Guide"
category: "workspace_permissions"
tags: ["workspace", "admin", "members", "settings", "roles", "audit"]
summary: "A complete guide to managing a CloudDesk workspace: members, permissions, settings, and security."
---

# Workspace Administration Guide

## Workspace Admin Responsibilities

As a workspace admin, you can:
- Invite and remove members
- Assign and change member roles
- Configure workspace settings (name, region, sharing rules)
- View the workspace audit log
- Manage integrations
- Reset member passwords and MFA

You **cannot** (only the workspace owner can):
- Change the billing plan
- Delete the workspace
- Transfer workspace ownership

## Inviting Members

1. Go to **Workspace Settings → Members → Invite**.
2. Enter the member's email address.
3. Select their role (Member or Admin).
4. Click **Send Invite**.

The invitee receives an email with a join link, valid for 7 days. If they don't join within 7 days, re-send the invite from the Members panel.

## Removing Members

1. Go to **Workspace Settings → Members**.
2. Find the member and click **Remove**.
3. Their access is revoked immediately. Their files remain in the workspace (they are not deleted).

## Viewing the Audit Log

The audit log shows all significant actions in your workspace for the past 90 days:
- File uploads, deletions, and shares
- Member joins and removals
- Settings changes
- API key creation and revocation

Access at **Workspace Settings → Security → Audit Log**. The log can be exported as CSV for compliance purposes.

## Workspace Settings Reference

| Setting | Default | Description |
|---|---|---|
| External Sharing | Off | Allow members to share files outside the org |
| Public Folder Links | Off | Allow creation of publicly accessible folder links |
| Guest Access | Off | Allow read-only guest users |
| File Versioning | 30 versions | Number of old versions to keep per file |
| Session Timeout | 8 hours | How long an inactive session stays signed in |
| IP Allowlist | None | Restrict access to specific IP ranges |

## IP Allowlist (Business/Enterprise)

The IP allowlist blocks CloudDesk access from any IP not on the list. Use with caution — if you add your office IP and then work from home, you will be locked out unless you add your home IP or disable the allowlist first.

## Transferring Ownership

To transfer workspace ownership:
1. Go to **Settings → Members → [target member] → Make Owner**.
2. Confirm the transfer. You become an Admin after the transfer.
3. The new owner receives an email confirmation.
