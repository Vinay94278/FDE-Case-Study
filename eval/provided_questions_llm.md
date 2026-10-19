# Answers to the provided questions (llm)

### Q-1: How do I reset my password?

- Expected source: D-01
- Outcome: **answered** (llm, llm_grounded_answer)
- Answer: Click the 'Forgot password?' link on the login screen, enter the email address associated with your account, then check your email for a reset link. Click the link, choose a new password that is at least 8 characters long and contains at least one number, and you’ll be logged out of all other active sessions.
- Source D-01.S1 (Resetting Your Password): "If you've forgotten your password, click 'Forgot password?' on the login screen and enter the email address associated with your account."
- Source D-01.S2 (Resetting Your Password): "We'll send you a reset link right away."
- Source D-01.S3 (Resetting Your Password): "Click the link and choose a new password that's at least 8 characters long, with at least one number."

### Q-2: How long do I have to use a password reset link before it expires?

- Expected source: D-01
- Outcome: **answered** (llm, llm_grounded_answer)
- Answer: Password reset links expire after 15 minutes.
- Source D-01.S6 (Resetting Your Password): "Note: password reset links expire after 15 minutes."

### Q-3: What's the maximum number of rows I can export to CSV?

- Expected source: D-03
- Outcome: **answered** (llm, llm_grounded_answer)
- Answer: The maximum number of rows you can export to CSV is 10,000.
- Source D-03.S5 (Exporting Reports to CSV): "Important limit: CSV exports are capped at 10,000 rows."

### Q-4: What are the API rate limits for the Growth plan?

- Expected source: D-06
- Outcome: **answered** (llm, llm_grounded_answer)
- Answer: Growth plans are limited to 60 requests per minute, per API key.
- Source D-06.S5 (API Rate Limits): "Rate limits: Growth plans are limited to 60 requests per minute, and Enterprise plans are limited to 300 requests per minute, per API key."

### Q-5: Can I connect Solstice to Salesforce?

- Expected source: none (docs do not cover it)
- Outcome: **not_covered** (llm, llm_not_covered)
- Answer: I don't have an answer for that in the documentation.
