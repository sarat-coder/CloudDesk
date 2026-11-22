---
title: "MFA Setup and Account Recovery"
category: "login_issue"
tags: ["mfa", "2fa", "account-recovery", "lockout", "authenticator", "totp"]
summary: "How to set up MFA, what to do if you're locked out, and how to recover your account after too many failed MFA attempts."
---

# MFA Setup and Account Recovery

## Supported MFA Methods

CloudDesk supports:
- **TOTP authenticator apps** (Google Authenticator, Authy, 1Password, etc.) — recommended
- **SMS one-time codes** — available but less secure
- **Hardware security keys** (FIDO2/WebAuthn) — Enterprise plan only

## Setting Up MFA

1. Go to **Settings → Security → Two-Factor Authentication**.
2. Click **Enable 2FA**.
3. Scan the QR code with your authenticator app.
4. Enter the 6-digit code shown in your app to confirm setup.
5. **Save your backup codes** — these are shown once and allow you to log in if you lose your authenticator device.

## Why TOTP Codes Fail

The most common reason TOTP codes fail is **clock drift** on the device running the authenticator app. TOTP codes are time-based and expire every 30 seconds. If your device's clock is more than 30 seconds off from the actual time, the codes will be rejected.

**Fix:**
1. On iOS: **Settings → General → Date & Time → Set Automatically** (enable).
2. On Android: **Settings → General Management → Date and Time → Automatic date and time** (enable).
3. After syncing the clock, wait 30 seconds and try a fresh code.

If the problem persists, generate a new code from scratch. If your app shows the code as still valid but CloudDesk rejects it, the account may be locked (see below).

## Account Lockout After Too Many Failed Attempts

After 5 consecutive failed MFA attempts, CloudDesk temporarily locks the account for **15 minutes** to prevent brute-force attacks.

After the lockout period:
1. Wait 15 minutes.
2. Try logging in again with a fresh TOTP code (ensure your phone clock is synced first).

## Using Backup Codes

If you do not have access to your authenticator app:
1. On the login screen, click **Use a backup code** instead of entering a TOTP.
2. Enter one of the 8-character backup codes you saved when setting up MFA.
3. Each backup code can only be used once.

If you have used all backup codes and have lost access to your authenticator app, contact support for account recovery.

## Account Recovery via Support

If you are locked out and have no backup codes:
1. Submit a support ticket from a verified email address associated with your account.
2. CloudDesk support will verify your identity using account ownership proofs (billing email, last 4 digits of card on file, etc.).
3. After verification, your MFA is reset and you must set it up again.

**Note**: Account recovery for high-security accounts (Business/Enterprise) requires confirmation from your workspace owner or admin.

## Revoking and Resetting MFA

Workspace admins can reset MFA for any member under **Workspace Settings → Members → [member] → Reset MFA**. This forces the member to re-enroll on next login.
