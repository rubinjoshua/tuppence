# Security Implementation Checklist

**Version:** 1.0
**Owner:** security-reviewer
**Purpose:** Quick reference checklist for developers implementing authentication

## Pre-Implementation

- [ ] Read `AUTH_SECURITY_ARCHITECTURE.md` completely
- [ ] Understand household isolation requirements
- [ ] Review OWASP Top 10 (https://owasp.org/Top10/)
- [ ] Set up development environment with HTTPS (even locally)

## Backend Implementation

### Password Security

- [ ] Install `argon2-cffi==23.1.0`
- [ ] Use correct Argon2id parameters:
  - `time_cost=3`
  - `memory_cost=65536`
  - `parallelism=4`
  - `hash_len=32`
  - `salt_len=16`
- [ ] Never log passwords (plaintext or hashed)
- [ ] Validate password strength on signup (min 8 chars recommended)
- [ ] Use `ph.verify()` for login checks (catches timing attacks)

### Session Management

- [ ] Create `sessions` table with all required fields
- [ ] Generate session IDs with `uuid.uuid4()` (not sequential)
- [ ] Set cookie flags correctly:
  - `httponly=True`
  - `secure=True` (HTTPS only)
  - `samesite="strict"`
- [ ] Implement 30-day expiration with sliding window
- [ ] Delete session on logout
- [ ] Clean up expired sessions daily (cron job)
- [ ] Store `household_id` in session (critical!)

### Database Isolation

- [ ] Add `household_id` to all relevant tables
- [ ] Create foreign key constraints to `households(id)`
- [ ] Implement middleware to inject `household_id` into request state
- [ ] **CRITICAL:** Filter EVERY query by `request.state.household_id`
- [ ] Test cross-household data access (must fail!)
- [ ] Add audit logging for queries in dev mode
- [ ] Never trust client-provided `household_id` - always use session value

### Token Security

- [ ] Use `secrets.token_urlsafe(24)` for invite tokens (192-bit entropy)
- [ ] Create `household_invites` table with all fields
- [ ] Set 7-day expiration on tokens
- [ ] Mark tokens as `redeemed=True` after use (one-time only)
- [ ] Never include household info in email subject/preview
- [ ] Validate token existence, expiration, and redemption status
- [ ] Delete or mark expired tokens as invalid

### Rate Limiting

- [ ] Install `slowapi==0.1.9`
- [ ] Configure limiter with Redis or in-memory backend
- [ ] Apply limits to:
  - `/auth/login` → 5/minute
  - `/auth/signup` → 3/hour
  - `/households/send_invite` → 5/day
  - `/households/join` → 10/hour
  - `/auth/reset_password` → 3/hour (if implemented)
- [ ] Return 429 status on rate limit exceeded
- [ ] Log rate limit violations

### API Endpoints

- [ ] Validate all input with Pydantic models
- [ ] Return generic error messages (don't leak info)
  - ✅ "Invalid email or password"
  - ❌ "Email not found" or "Password incorrect"
- [ ] Use HTTP status codes correctly:
  - 200 OK - Success
  - 400 Bad Request - Invalid input
  - 401 Unauthorized - Not logged in
  - 403 Forbidden - Access denied
  - 429 Too Many Requests - Rate limited
- [ ] Never return password hashes in responses
- [ ] Include CSRF token in forms (if using HTML forms)

### Database Queries

- [ ] Use SQLAlchemy ORM (parameterized queries)
- [ ] Never use raw SQL with f-strings or string concatenation
- [ ] Always filter by `household_id`:
  ```python
  # CORRECT
  db.query(LedgerEntry).filter(
      LedgerEntry.household_id == request.state.household_id,
      LedgerEntry.year == year
  )

  # WRONG - Security violation!
  db.query(LedgerEntry).filter(
      LedgerEntry.year == year
  )
  ```
- [ ] Test with multiple households to verify isolation

### Email Security

- [ ] Choose email provider (SendGrid, AWS SES, Mailgun)
- [ ] Use TLS for SMTP connections
- [ ] Validate email format before sending
- [ ] Rate limit email sending (5/day per user)
- [ ] Include unsubscribe link (if sending notifications)
- [ ] Log email sends for audit trail
- [ ] Handle email failures gracefully (don't expose errors to user)

### Error Handling

- [ ] Catch all exceptions in route handlers
- [ ] Log errors server-side with full details
- [ ] Return generic error messages to client
- [ ] Never expose:
  - Stack traces
  - Database errors
  - File paths
  - Internal system info
- [ ] Use structured logging (JSON format)

## Frontend Implementation

### Authentication State

- [ ] Store session cookie (automatic with HTTP-only)
- [ ] Never store passwords locally
- [ ] Clear auth state on logout
- [ ] Handle 401 responses (redirect to login)
- [ ] Implement session expiration UI (show "session expired" message)

### Input Validation

- [ ] Validate email format client-side (basic check)
- [ ] Enforce password requirements client-side (UX)
- [ ] Show password strength indicator
- [ ] Prevent empty form submissions
- [ ] Sanitize user input before display (prevent XSS)

### Secure Communication

- [ ] Use HTTPS for all API calls
- [ ] Pin SSL certificate (optional, iOS best practice)
- [ ] Handle network errors gracefully
- [ ] Don't log credentials in debug mode
- [ ] Use App Transport Security (ATS) on iOS

### Error Messages

- [ ] Show user-friendly error messages
- [ ] Don't reveal security details:
  - ✅ "Login failed. Please check your credentials."
  - ❌ "Account locked after 5 failed attempts."
- [ ] Implement loading states (prevent double-submit)

## Database Migrations

### Migration Scripts

- [ ] Use Alembic for migrations
- [ ] Add `household_id` columns as nullable first
- [ ] Backfill existing data with default `household_id=1`
- [ ] Make `household_id` NOT NULL after backfill
- [ ] Add foreign key constraints last
- [ ] Test migrations on local database first
- [ ] Create rollback scripts for each migration
- [ ] Version migration scripts (e.g., `001_add_users_table.py`)

### Data Migration

- [ ] Backup production database before migration
- [ ] Test migrations on staging environment
- [ ] Plan downtime window (if needed)
- [ ] Monitor database performance during migration
- [ ] Verify data integrity after migration

## Security Testing

### Unit Tests

- [ ] Test password hashing (hash != plaintext)
- [ ] Test password verification (correct vs incorrect)
- [ ] Test session creation and expiration
- [ ] Test token generation (uniqueness, entropy)
- [ ] Test rate limiting (exceeding limits)
- [ ] Test household filtering (cannot access other household data)

### Integration Tests

- [ ] Test full signup flow
- [ ] Test full login flow
- [ ] Test logout (session deleted)
- [ ] Test household switching
- [ ] Test invite sending and redemption
- [ ] Test leaving household
- [ ] Test cross-household data isolation

### Security Tests

- [ ] Try accessing another household's data (must fail)
- [ ] Try guessing invite tokens (must fail)
- [ ] Try SQL injection in inputs (must fail)
- [ ] Try XSS in text fields (must be sanitized)
- [ ] Try session hijacking (test cookie security)
- [ ] Try brute force login (rate limit must trigger)
- [ ] Verify HTTPS enforcement (HTTP must redirect)

### Penetration Testing

- [ ] Run OWASP ZAP or Burp Suite scan
- [ ] Test for common vulnerabilities:
  - SQL Injection
  - XSS
  - CSRF
  - Authentication bypass
  - Session fixation
  - Privilege escalation
- [ ] Document findings and fixes

## Deployment

### Environment Variables

- [ ] Set `DATABASE_URL` (PostgreSQL connection string)
- [ ] Set `OPENAI_API_KEY` (if using AI features)
- [ ] Set `SECRET_KEY` for session signing (generate securely!)
- [ ] Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` (email)
- [ ] Set `ALLOWED_ORIGINS` for CORS (restrict to iOS app)
- [ ] Never commit `.env` file to git

### HTTPS Configuration

- [ ] Verify HTTPS is enabled (Railway does this automatically)
- [ ] Test SSL certificate validity
- [ ] Redirect HTTP to HTTPS
- [ ] Set HSTS header (`Strict-Transport-Security`)
- [ ] Verify cookie `secure` flag works

### Monitoring

- [ ] Set up logging (structured JSON logs)
- [ ] Monitor failed login attempts
- [ ] Monitor rate limit violations
- [ ] Monitor database query performance
- [ ] Set up alerts for security events:
  - Multiple failed logins from same IP
  - Unusual household access patterns
  - High rate of invite sends
  - Database errors

### Backup & Recovery

- [ ] Enable automatic database backups (Railway feature)
- [ ] Test database restore process
- [ ] Document recovery procedures
- [ ] Keep backups for 30 days minimum

## Code Review Checklist

### Before Submitting PR

- [ ] All items above checked
- [ ] No hardcoded secrets in code
- [ ] No TODO comments with security implications
- [ ] All new code has tests
- [ ] All tests pass
- [ ] No debug print statements
- [ ] Dependencies pinned in `requirements.txt`

### During Code Review

- [ ] Review for SQL injection risks
- [ ] Review for XSS risks
- [ ] Review for authentication bypass
- [ ] Review for authorization bypass (household isolation)
- [ ] Review for sensitive data exposure
- [ ] Review error handling (no info leaks)

## Resources

- **OWASP Top 10:** https://owasp.org/Top10/
- **Argon2 Spec:** https://github.com/P-H-C/phc-winner-argon2
- **FastAPI Security:** https://fastapi.tiangolo.com/tutorial/security/
- **SQLAlchemy Security:** https://docs.sqlalchemy.org/en/20/faq/security.html
- **Architecture Doc:** `AUTH_SECURITY_ARCHITECTURE.md`

## Contact

**Questions or concerns?** Message `@security-reviewer` for guidance.

---

**This checklist must be completed before releasing authentication to production.**
