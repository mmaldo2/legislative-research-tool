---
status: complete
priority: p3
issue_id: "100"
tags: [code-review, security]
dependencies: []
---

# Plaintext Signing Secret

## Problem

WebhookEndpoint.secret stored as plaintext String in PostgreSQL. If database is compromised, all signing secrets are exposed enabling signature forgery.

## Files

- src/models/webhook_endpoint.py:24

## Solution

Encrypt secrets at rest using application-level encryption (Fernet with key from env/KMS). Decrypt only at delivery time in sign_payload(). Fast-follow item -- acceptable for initial release with documented threat model.
