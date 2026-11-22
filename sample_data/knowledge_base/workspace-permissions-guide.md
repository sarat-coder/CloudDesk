---
title: "Workspace Permissions and External Sharing"
category: "workspace_permissions"
tags: ["permissions", "external-sharing", "workspace", "admin", "roles", "sharing"]
summary: "How workspace permissions work in CloudDesk and how to enable external sharing."
---

# Workspace Permissions and External Sharing

## Workspace Roles

Each workspace member has one of three roles:

| Role | Permissions |
|---|---|
| **Owner** | Full control: settings, billing, member management, deletion |
| **Admin** | Member management, settings (except billing and deletion) |
| **Member** | Create, edit, share files. Cannot change settings |
| **Guest** | Read-only access to specific shared folders |

## Enabling External Sharing

External sharing allows members to share files or folders with people outside your organization.

**Why is the toggle greyed out?**

The External Sharing toggle may be greyed out for two reasons:

1. **Plan restriction**: External sharing is only available on **Pro, Business, and Enterprise** plans. Free plan workspaces cannot enable it.
2. **Admin not signed in**: Only workspace admins and owners can toggle this setting.

**To enable external sharing:**

1. Sign in as a workspace Admin or Owner.
2. Go to **Workspace Settings → Permissions → Sharing**.
3. Toggle **Allow External Sharing** to On.
4. Optionally, restrict to specific email domains: **Allow sharing only with @yourdomain.com**.
5. Click **Save**.

Members can now share files and folders with external email addresses.

## Share Link Settings

When sharing externally, members choose the link permission:
- **View only**: Recipient can view but not edit.
- **Comment**: Recipient can view and add comments.
- **Edit**: Recipient can make changes (use with caution).

Links can be set to expire after a specified number of days.

## Revoking External Access

To revoke access:
1. Navigate to the file or folder.
2. Click **Share → Manage Access**.
3. Remove the external user or disable the share link.

## Audit of External Shares

Workspace admins can see all active external shares under **Settings → Security → External Shares**. This list shows who shared what, with whom, and when.

## Plan-Based Restrictions

| Plan | External Sharing |
|---|---|
| Free | Not available |
| Pro | Available |
| Business | Available, with domain restrictions |
| Enterprise | Available, with domain restrictions and audit |
