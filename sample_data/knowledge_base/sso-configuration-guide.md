---
title: "SSO Configuration Guide"
category: "login_issue"
tags: ["sso", "saml", "okta", "azure-ad", "authentication", "enterprise"]
summary: "How to set up and troubleshoot SAML-based SSO for CloudDesk Enterprise workspaces."
---

# SSO Configuration Guide

Single Sign-On (SSO) lets your team log in to CloudDesk using your company's existing identity provider (IdP), such as Okta, Azure AD, or Google Workspace. This guide covers setup, common errors, and troubleshooting steps.

## Supported Protocols

CloudDesk supports SAML 2.0. OAuth/OIDC SSO is not currently available.

## Setup Steps

1. **Navigate to Workspace Settings → Security → Single Sign-On.**
2. Click **Enable SSO** and select your IdP from the dropdown.
3. Copy the **CloudDesk ACS URL** and **Entity ID** into your IdP's application settings.
4. Download the **IdP Metadata XML** from your identity provider and upload it to CloudDesk.
5. Click **Test SSO** to verify the configuration before enabling it for all users.
6. Once the test succeeds, toggle **Require SSO for all members** to enforce SSO.

## Common Error: "Invalid Assertion Signature"

This error means the SAML assertion CloudDesk received does not match the signing certificate uploaded in your IdP metadata.

**Causes:**
- The IdP certificate has expired and a new one was issued.
- The wrong metadata XML was uploaded.
- The IdP rotated its signing key.

**Fix:**
1. Log in to your identity provider as an admin.
2. Navigate to the SSO application and check the certificate expiry date.
3. If expired, renew the certificate.
4. Download the **updated metadata XML** from your IdP.
5. In CloudDesk, go to **Settings → Security → SSO** and re-upload the metadata.
6. Click **Test SSO** to confirm the fix.

## Common Error: "User not found"

The user's email in the SAML assertion does not match any CloudDesk account.

**Fix:** Ensure the IdP sends the email attribute in the SAML assertion and that it matches the email used to invite the user to CloudDesk.

## Requiring SSO After Setup

Once SSO is enforced, password-based login is disabled for workspace members. Exceptions: workspace owners can always log in with a password as a break-glass option.

## Plan Requirement

SSO requires the **Business** or **Enterprise** plan.
