# Brevo Email Setup Guide

## Prerequisites

- A Brevo account (https://www.brevo.com/)
- Verified sender email in Brevo
- A domain or subdomain for receiving emails (e.g., `reply.yourdomain.com`)

---

## 1. Create Brevo Account & API Key

1. Sign up at https://www.brevo.com/
2. Go to **SMTP & API** → **API Keys**
3. Click **Create a new API key**
4. Copy the key (starts with `xkeysib-`)
5. Add it to your `.env` file:

```env
BREVO_API_KEY=xkeysib-your-api-key-here
```

---

## 2. Verify Sender Email

1. In Brevo, go to **Senders** → **Add a new sender**
2. Enter your sender email and name
3. Verify the email via the confirmation link Brevo sends
4. Add to `.env`:

```env
BREVO_SENDER_EMAIL=support@yourdomain.com
BREVO_SENDER_NAME=Help Desk Support
```

---

## 3. Configure Outgoing Email (SENDING)

No additional SMTP configuration is needed. The application sends emails directly via the Brevo Transactional Email API (`https://api.brevo.com/v3/smtp/email`).

The following emails are sent automatically:

- **Forgot Password** — when a user requests a password reset
- **Ticket Closed** — when a ticket status changes to `Closed`
- **Ticket Reply** — when an agent/manager replies to a customer ticket
- **Ticket Assignment** — when a ticket is assigned to an agent

All outgoing emails use `BREVO_SENDER_EMAIL` and `BREVO_SENDER_NAME`.

---

## 4. Configure Inbound Email (RECEIVING)

To receive customer replies by email, you must set up Brevo Inbound Parsing.

### 4.1 Enable Inbound Parsing in Brevo

1. In Brevo, go to **Inbound Parsing**
2. Click **Enable Inbound Parsing**
3. Select your domain/subdomain (e.g., `reply.yourdomain.com`)
4. Brevo will provide DNS records (MX records) to add to your domain

### 4.2 Configure DNS

Add the MX records provided by Brevo to your DNS settings:

| Type | Host/Name | Priority | Value/Points to |
|------|-----------|----------|-----------------|
| MX   | `reply.yourdomain.com` | 10 | `inbound.brevo.com` |

Wait for DNS propagation (usually 5–30 minutes).

### 4.3 Configure Webhook

1. In Brevo Inbound Parsing settings, add a webhook URL:
   ```
   https://YOUR_PUBLIC_DOMAIN/api/email/brevo/inbound
   ```
2. Set the webhook method to **POST**
3. Add a webhook secret token in `.env`:
   ```env
   BREVO_INBOUND_WEBHOOK_TOKEN=your-random-secret-here
   ```
4. Enter the same token in the Brevo webhook settings as the verification token

### 4.4 Local Testing with ngrok

For local development, expose your Flask app publicly:

```bash
ngrok http 5000
```

Use the ngrok HTTPS URL as your webhook URL (e.g., `https://abc123.ngrok.io/api/email/brevo/inbound`).

---

## 5. Environment Variables

Required `.env` variables:

```env
# Brevo API
BREVO_API_KEY=xkeysib-your-api-key-here
BREVO_SENDER_EMAIL=support@yourdomain.com
BREVO_SENDER_NAME=Help Desk Support
BREVO_REPLY_DOMAIN=reply.yourdomain.com
BREVO_INBOUND_WEBHOOK_TOKEN=your-random-secret-here
```

---

## 6. Restart Application

After updating `.env`, restart the Flask application:

```bash
python app.py
```

---

## 7. Test Outgoing Email

1. Request a password reset from the login page
2. Create a ticket and close it
3. Reply to a ticket as an agent
4. Verify emails arrive in the recipient inbox

---

## 8. Test Incoming Email

1. Send an email to `ticket-TKT202508200001@reply.yourdomain.com` (use an actual ticket number from your system)
2. The sender email must match the ticket requester's email in the database
3. Verify the comment appears in the ticket
4. Verify the ticket reopens if it was `Closed`

---

## 9. Troubleshooting

| Issue | Solution |
|-------|----------|
| Brevo API 401 | Check `BREVO_API_KEY` in `.env` |
| Brevo API 403 | Verify sender email in Brevo dashboard |
| Email not sending | Check Flask logs for `Brevo email failed` |
| Webhook not receiving | Verify public HTTPS URL and DNS MX records |
| Webhook 403 | Check `BREVO_INBOUND_WEBHOOK_TOKEN` matches in Brevo and `.env` |
| Duplicate comments | Check `email_inbound_log` table for deduplication |
| Ticket not found from reply | Ensure `BREVO_REPLY_DOMAIN` is correct |

---

## 10. Security Notes

- Never commit real API keys to source control
- Use strong random values for `BREVO_INBOUND_WEBHOOK_TOKEN`
- The inbound webhook validates:
  - Webhook token
  - Sender email matches ticket requester
  - Ticket exists
  - Duplicate emails are rejected
