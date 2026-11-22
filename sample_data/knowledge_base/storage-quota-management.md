---
title: "Storage Quota Management"
category: "storage_quota"
tags: ["storage", "quota", "upload", "free-plan", "upgrade", "deletion"]
summary: "How CloudDesk storage quotas work, why the quota meter may lag after deletions, and how to manage storage."
---

# Storage Quota Management

## Storage Limits by Plan

| Plan | Storage |
|---|---|
| Free | 5 GB |
| Pro | 100 GB |
| Business | 500 GB |
| Enterprise | 2,000 GB |

Storage is per workspace. If you have multiple workspaces, each has its own quota.

## Why Does the Quota Meter Lag After Deletions?

When you delete files, the storage system marks them for removal but does **not immediately reclaim the space**. The quota meter updates within **15 minutes** as the background deletion job processes the queue.

If the meter still shows the same usage after 30 minutes, the files may be in the **Trash** (not yet permanently deleted).

## How to Free Up Space

1. **Empty the Trash**: Go to **Files → Trash** and click **Empty Trash**. This permanently deletes all trashed items and triggers the quota recalculation.
2. **Delete large files directly**: Files larger than 100 MB show up under **Settings → Storage → Large Files**. Review and delete files you no longer need.
3. **Remove old file versions**: CloudDesk keeps up to 30 previous versions of each file. Go to **File → Version History** and delete old versions.
4. **Upgrade your plan**: If you consistently need more storage, consider upgrading.

## What Happens When You Hit the Limit?

- New uploads are blocked with the error "Storage quota exceeded."
- Existing files are not affected; you can still read, share, and delete them.
- Collaborators in your workspace can still access shared files.

## Quota Accuracy

The quota displayed in the UI reflects your usage as of the last calculation job. During high load, this may be up to 15 minutes behind actual usage. Do not rely on the meter for precise real-time tracking.

## Upgrading Storage

To increase your storage limit, upgrade your plan at **Settings → Billing → Change Plan**. The new storage is available immediately upon payment confirmation.
