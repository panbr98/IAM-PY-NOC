# Security Model

- local credentials first with MFA-ready extension points
- signed bearer tokens for API calls
- hashed passwords using PBKDF2-HMAC
- backend-authoritative permissions and state transitions
- encrypted secrets helper for connector credentials
- audit trail for authentication, approvals, provisioning, delegations, and emergency termination
- certificate fingerprint capture in the client profile model for trust-on-first-use bootstrap
