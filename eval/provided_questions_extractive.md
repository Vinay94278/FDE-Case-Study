# Answers to the provided questions (extractive)

### Q-1: How do I reset my password?

- Expected source: D-01
- Outcome: **answered** (extractive, extractive_best_sentences)
- Answer: If you've forgotten your password, click 'Forgot password?' on the login screen and enter the email address associated with your account. Click the link and choose a new password that's at least 8 characters long, with at least one number.
- Source D-01.S1 (Resetting Your Password): "If you've forgotten your password, click 'Forgot password?' on the login screen and enter the email address associated with your account."
- Source D-01.S3 (Resetting Your Password): "Click the link and choose a new password that's at least 8 characters long, with at least one number."

### Q-2: How long do I have to use a password reset link before it expires?

- Expected source: D-01
- Outcome: **answered** (extractive, extractive_best_sentences)
- Answer: Note: password reset links expire after 15 minutes. If yours has expired, don't try to reuse the old email -- just go back to the login page and request a brand new reset link.
- Source D-01.S6 (Resetting Your Password): "Note: password reset links expire after 15 minutes."
- Source D-01.S7 (Resetting Your Password): "If yours has expired, don't try to reuse the old email -- just go back to the login page and request a brand new reset link."

### Q-3: What's the maximum number of rows I can export to CSV?

- Expected source: D-03
- Outcome: **answered** (extractive, extractive_best_sentences)
- Answer: Important limit: CSV exports are capped at 10,000 rows. If your report has more rows than that, apply additional filters to narrow it down, or contact support about a bulk data export instead.
- Source D-03.S5 (Exporting Reports to CSV): "Important limit: CSV exports are capped at 10,000 rows."
- Source D-03.S6 (Exporting Reports to CSV): "If your report has more rows than that, apply additional filters to narrow it down, or contact support about a bulk data export instead."

### Q-4: What are the API rate limits for the Growth plan?

- Expected source: D-06
- Outcome: **answered** (extractive, extractive_best_sentences)
- Answer: Rate limits: Growth plans are limited to 60 requests per minute, and Enterprise plans are limited to 300 requests per minute, per API key. Exceeding the limit returns an HTTP 429 response.
- Source D-06.S5 (API Rate Limits): "Rate limits: Growth plans are limited to 60 requests per minute, and Enterprise plans are limited to 300 requests per minute, per API key."
- Source D-06.S6 (API Rate Limits): "Exceeding the limit returns an HTTP 429 response."

### Q-5: Can I connect Solstice to Salesforce?

- Expected source: none (docs do not cover it)
- Outcome: **not_covered** (extractive, relevance_gate_failed)
- Answer: I don't have an answer for that in the documentation.
