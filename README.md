# Aurora Banff

A live conditions tracker for the aurora borealis around Banff National Park.
It shows real-time geomagnetic activity (Kp index) and cloud cover, lists the
best nearby viewing spots, and texts subscribers when conditions turn
favourable or change significantly.

## What it does

- **Live conditions dashboard** — current Kp index (with a plain-language
  "how good is it" read-out and a mini history sparkline), current cloud
  cover, temperature, and a tonight's-cloud-trend bar chart.
- **Viewing spots** — five curated locations within a ~25 minute drive of the
  Banff townsite, each with driving time, compass direction, and a one-tap
  map link.
- **Text message alerts** — anyone can subscribe with their phone number and
  choose their own thresholds. Two kinds of alerts go out:
  1. **Aurora alert** — sent when the Kp index and cloud cover both cross
     the subscriber's chosen thresholds at the same time (good conditions).
  2. **Cloud change alert** — sent whenever cloud cover shifts by more than
     the subscriber's chosen number of percentage points since the last
     check, in either direction.
- **No paid data required** — aurora data comes from NOAA's Space Weather
  Prediction Center and weather data comes from Open-Meteo. Both are free
  and need no API key. SMS sending can use either Twilio (paid) or free
  email-to-SMS gateways via carrier domains.

## Project layout

```
aurora-tracker/
├── app.py                  Flask app factory + routes
├── wsgi.py                 Entry point for gunicorn (the web app only)
├── scheduler.py            Alert-checking logic
├── scheduler_runner.py     Standalone entry point that runs the checker on a timer
├── config.py                Settings loaded from environment variables
├── models.py                 Subscriber database model
├── services/
│   ├── aurora_service.py   NOAA Kp index fetching
│   ├── weather_service.py  Open-Meteo cloud cover fetching
│   ├── sms_service.py      Twilio SMS wrapper
│   └── locations.py        Viewing spot data
├── templates/               HTML templates
├── static/                  CSS and JS
├── deploy/                  systemd + nginx config examples for production
├── requirements.txt
└── .env.example             Copy to .env and fill in
```

## Running it locally

```bash
python3 -m venv venv
source venv/bin/activate          # venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env
# edit .env - at minimum set SECRET_KEY; for SMS alerts, configure either
# Twilio credentials or SMTP settings for email-to-SMS gateways

python app.py
```

Visit `http://localhost:1324`. In this local dev mode, the alert checker runs
inside the same process as the web server, on the interval set by
`CHECK_INTERVAL_MINUTES` in `.env`.

## Setting up SMS alerts

You have two options for sending SMS alerts:

### Option 1: Free email-to-SMS gateways

1. Set up an email account with SMTP access (e.g., Gmail)
2. Generate an app password if using 2FA (Gmail: https://support.google.com/accounts/answer/185833)
3. Put SMTP settings in `.env`:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_EMAIL=your_email@gmail.com
   SMTP_PASSWORD=your_app_password_here
   ```
4. Subscribers select their carrier when signing up - the system sends SMS
   via the carrier's email-to-SMS gateway (e.g., number@vtext.com for Verizon)

### Option 2: Twilio (paid)

1. Create a free account at https://www.twilio.com and buy or use a trial
   phone number capable of sending SMS.
2. From the Twilio console, copy your **Account SID**, **Auth Token**, and
   your **Twilio phone number**.
3. Put them in `.env`:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token_here
   TWILIO_FROM_NUMBER=+15555555555
   ```
4. Trial Twilio accounts can only text phone numbers you've manually
   verified in the console. Upgrade the account to text anyone.

**Note:** The system tries email-to-SMS first if a subscriber has selected a carrier,
and falls back to Twilio if email-to-SMS fails or no carrier is set.

## Deploying to your own domain

This is one straightforward way to run it on a Linux server (Ubuntu/Debian)
that you already point your domain at. Adjust paths/usernames as needed.

### 1. Get the code on the server

```bash
sudo mkdir -p /var/www/aurora-tracker
sudo chown $USER:$USER /var/www/aurora-tracker
# copy the project files into /var/www/aurora-tracker, e.g. via scp, git, or rsync

cd /var/www/aurora-tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # fill in SECRET_KEY, SMTP or Twilio credentials, etc.
```

### 2. Run the web app with gunicorn, behind nginx

Copy `deploy/aurora-tracker.service` to `/etc/systemd/system/` and
`deploy/nginx.conf.example` to `/etc/nginx/sites-available/aurora-tracker`
(edit `yourdomain.com` to your real domain first), then:

```bash
sudo mkdir -p /var/log/aurora-tracker
sudo chown www-data:www-data /var/log/aurora-tracker /var/www/aurora-tracker

sudo ln -s /etc/nginx/sites-available/aurora-tracker /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

sudo systemctl daemon-reload
sudo systemctl enable --now aurora-tracker
```

### 3. Run the alert scheduler as its own single process

**Important:** run exactly one instance of the scheduler. The web app itself
does not start it (see the note in `app.py`) so that scaling gunicorn to
multiple workers never sends anyone a duplicate text.

```bash
sudo systemctl enable --now aurora-tracker-scheduler
```

### 4. Point your domain at the server and enable HTTPS

Make sure your domain's DNS A record points at the server's IP address,
then run:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot will fetch a free certificate and update the nginx config to serve
over HTTPS and redirect HTTP to HTTPS automatically.

### Checking logs

```bash
sudo journalctl -u aurora-tracker -f              # web app
sudo journalctl -u aurora-tracker-scheduler -f    # alert checker
```

## Notes and limitations

- The Kp-to-visibility guidance in `services/aurora_service.py` is a
  general rule-of-thumb for Banff's latitude, not a guarantee — local
  conditions (light pollution, terrain, moon phase) still matter.
- The default SQLite database (`aurora.db`) is fine for a single-server
  deployment. If you outgrow it, point `DATABASE_URL` in `.env` at a
  Postgres or MySQL instance instead — no code changes required.
- Phone numbers must be entered in international format (e.g. `+14035551234`).
- To honour SMS opt-outs properly beyond this app's own unsubscribe link,
  configure Twilio's built-in STOP/START keyword handling if using Twilio.
- Email-to-SMS gateways may have rate limits or reliability issues depending
  on the carrier. Twilio is more reliable but costs money.
