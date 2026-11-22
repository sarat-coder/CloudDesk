---
title: "Security Incident Response"
category: "security"
tags: ["security", "breach", "suspicious-login", "account-compromise", "2fa", "incident"]
summary: "What to do if you suspect your CloudDesk account has been compromised or you detect unauthorized access."
---

# Security Incident Response

## Immediate Actions if You Suspect a Breach

If you believe your account has been compromised, take these steps immediately:

1. **Force-sign-out all sessions**: Go to **Settings → Security → Active Sessions** and click **Sign Out All Devices**.
2. **Change your password**: Go to **Settings → Security → Password** and set a new, strong password.
3. **Review and revoke API keys**: Go to **Settings → API → API Keys** and revoke any keys you do not recognize.
4. **Enable or verify 2FA**: Ensure two-factor authentication is active on all accounts.
5. **Contact CloudDesk Support immediately**: Submit a security ticket so we can investigate from our side.

## What CloudDesk Does During a Security Investigation

Upon receiving a security incident report, CloudDesk will:
1. Flag the account for security review.
2. Audit login activity for the past 90 days.
3. Identify IP addresses and sessions involved.
4. Notify you of findings within 24 hours.
5. Coordinate with your security team on remediation.

## Reviewing Login Activity

Under **Settings → Security → Login History**, you can see:
- Timestamp of each login
- IP address and approximate location
- Device and browser
- Login method (password, SSO, API key)

Report any entries you do not recognize to support immediately.

## Suspicious IP Indicators

CloudDesk's security system flags logins from:
- Locations geographically distant from normal usage
- Known malicious IP ranges
- Anonymizing proxies or Tor exit nodes

These are marked with a warning icon in Login History.

## Enterprise Security Escalation

For Enterprise customers, security incidents are automatically escalated to the **Security Response Team**. The response SLA for critical security incidents is:
- **Initial acknowledgement**: 1 hour
- **Active investigation**: 4 hours
- **Status update**: Every 2 hours until resolved

## Data Access During a Potential Breach

CloudDesk cannot confirm what data was accessed during an unauthorized session without a full forensic investigation. Submit a formal Data Breach Notification request and we will provide a written report within 72 hours (as required by GDPR Article 33).
