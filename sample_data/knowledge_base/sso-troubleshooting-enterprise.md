---
title: "SSO Troubleshooting for Enterprise Customers"
category: "login_issue"
tags: ["sso", "saml", "enterprise", "okta", "azure-ad", "troubleshooting", "metadata"]
summary: "Deep-dive troubleshooting for enterprise SSO issues including certificate errors, metadata refresh, and IdP-specific guidance."
---

# SSO Troubleshooting for Enterprise Customers

## Diagnosing SAML Errors

CloudDesk returns specific error codes for SSO failures. The error code is shown on the login error screen and included in audit logs.

| Error Code | Meaning | Fix |
|---|---|---|
| `SAML_INVALID_SIGNATURE` | Signing certificate mismatch | Re-upload IdP metadata |
| `SAML_ASSERTION_EXPIRED` | Assertion issued more than 5 minutes ago | Check clock sync on IdP server |
| `SAML_AUDIENCE_MISMATCH` | Entity ID in IdP does not match CloudDesk | Update Entity ID in IdP config |
| `SAML_ACS_MISMATCH` | ACS URL in IdP does not match CloudDesk | Update ACS URL in IdP config |
| `SAML_USER_NOT_FOUND` | Email in assertion not in CloudDesk | Invite user to workspace first |
| `SAML_NO_EMAIL` | IdP not sending email attribute | Add email attribute mapping in IdP |

## Okta-Specific Steps

**Updating a rotated certificate in Okta:**
1. In Okta Admin → Applications → CloudDesk App → Sign On tab.
2. Under "SAML Signing Certificates," click "Generate new certificate."
3. Activate the new certificate.
4. Download the new metadata XML.
5. Upload it to CloudDesk under **Settings → Security → SSO → Update Metadata**.

**Checking attribute mapping in Okta:**
1. In the CloudDesk app, go to the Sign On tab → Attributes section.
2. Confirm there is a mapping: `user.email → email`.
3. Add if missing, then test.

## Azure AD-Specific Steps

**Rotating expired certificates in Azure AD:**
1. Go to Azure Portal → Enterprise Applications → CloudDesk.
2. Under **Single Sign-On → SAML Certificates**, click **Edit**.
3. Create a new certificate and activate it.
4. Download the **Federation Metadata XML**.
5. Upload to CloudDesk.

## Active Directory Attributes

CloudDesk requires these SAML attributes:
- `email` or `http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress` — mandatory
- `displayName` — used as user's full name in CloudDesk
- `groups` — optional, for group-based role assignment

## Verifying the Fix Without Logging Out Current Users

Before switching users to the new certificate:
1. Keep the old metadata active.
2. Enable the new metadata in test mode: **Settings → Security → SSO → Test New Metadata**.
3. Use the **Test SSO** button (which uses a service account) to verify.
4. Once confirmed, activate the new metadata for all users.
5. Remove the old metadata.

## Enterprise SLA for SSO Outages

SSO outages that affect your entire workforce are classified as **Critical** severity. Under the Enterprise SLA:
- Response: 30 minutes
- Initial mitigation: 2 hours
- Root-cause analysis: 48 hours post-resolution

If you are experiencing a full SSO outage, call the enterprise support hotline in your onboarding documentation. Do not wait for email responses.
