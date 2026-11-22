---
title: "Account Deletion and GDPR Data Erasure"
category: "account"
tags: ["gdpr", "deletion", "right-to-erasure", "data-privacy", "workspace-deletion", "account"]
summary: "How to delete a CloudDesk workspace, what GDPR right-to-erasure requests require, and the data deletion process."
---

# Account Deletion and GDPR Data Erasure

## Deleting a Workspace

To delete a workspace:
1. Go to **Workspace Settings → Danger Zone → Delete Workspace**.
2. Type the workspace name to confirm.
3. Click **Delete**.

**What happens:**
- All files, messages, comments, and settings in the workspace are permanently deleted.
- Members lose access immediately.
- The workspace slug is released and may be claimed by another user.
- Billing for the workspace stops at the end of the current billing cycle.

**What is NOT automatically deleted by workspace deletion:**
- User account profiles
- Billing records (retained for 7 years for legal compliance)
- Audit logs (retained for 90 days)
- Backups (purged according to your plan's backup retention schedule)

## GDPR Right to Erasure (Article 17)

Under GDPR, customers have the right to request permanent erasure of their personal data.

**What CloudDesk erases in a formal erasure request:**
- All files and content in the specified workspace(s)
- Personal identifiable information (PII) from user profiles
- Activity logs referencing the data subject
- Backups (erased within 30 days of the written backups rotation schedule)
- Marketing preferences and communications history

**What CloudDesk retains under legal obligation:**
- Financial records (invoices, payment history) — 7 years
- Security/fraud investigation records — per applicable law
- Records needed for active legal disputes

## How to Submit a GDPR Erasure Request

1. Submit a support ticket with subject "GDPR Data Erasure Request."
2. Include: the requesting individual's name and email, the workspace slug(s) to be deleted, authorization from your Data Protection Officer (DPO).
3. CloudDesk will verify the request with your account owner within 5 business days.
4. Erasure is completed within 30 days of verification, as required by GDPR Article 17(1).
5. A written **Certificate of Erasure** is issued upon completion.

## Certificate of Erasure

A certificate of erasure is provided for all formal GDPR erasure requests. It includes:
- Date of erasure
- Data categories erased
- Storage systems purged
- Confirmation that backups have been or are scheduled for removal

## Enterprise SLA for Data Deletion

Enterprise customers have a contractual SLA of:
- **Response**: 2 business days
- **Completion**: 15 business days (faster than the statutory 30-day requirement)
- **Certificate delivery**: Within 5 business days of completion
