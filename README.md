Bingosync.com
===

This is the repository powering [bingosync.com](http://bingosync.com/),
a web application that lets people collaboratively work on "bingo boards"
when speedrunning games.

For more information on speedrunning and bingo, you can read:
  - [the bingosync about page](http://bingosync.com/about)
  - [the speedrunslive faq](https://www.speedrunslive.com/rules-faq/faq)
  - [the about section of an SRL bingo card](https://www.speedrunslive.com/tools/bingo/oot)

#### Fun Implementation Details! :D

Bingosync is implemented using a combination of the [django](https://www.djangoproject.com/)
and [tornado](http://www.tornadoweb.org/) web servers. The django web server
(bingosync-app) hosts the main website content, serves most of the pages,
and talks to the database. The tornado web server (bingosync-websocket)
maintains all websocket connections to the site and passes messages along
to the clients in a "publish and subscribe" kind of model.

The actual site is hosted on one of my personal machines. It's running behind 
an [nginx](http://wiki.nginx.org/Main) proxy that serves static files and splits
traffic to the django and tornado servers. I use [postgres](http://www.postgresql.org/)
for the database. Conveniently, this machine is the same one that I run 
[bingobot](https://github.com/kbuzsaki/bingobot) off of. Maybe there's some 
opportunity for integration there in the future :)

#### Getting Started

See [README-DEV.md](README-DEV.md) for development setup instructions.

We use `pyproject.toml` with `uv` for fast dependency management (10-100x faster than pip).

#### Database Requirements

This platform requires **PostgreSQL 15 or later** as the database backend. SQLite is not supported.

**Environment Configuration:**

You must set the `DATABASE_URL` environment variable to a valid PostgreSQL connection string:

```bash
export DATABASE_URL="postgresql://username:password@localhost:5432/bingosync"
```

**Docker Deployment:**

The included `docker-compose.yml` automatically configures PostgreSQL. See the deployment documentation for details.


#### Email Configuration

The platform uses email for user registration and password reset functionality. Email configuration is required for production deployments.

**Development Mode:**

In development (when `DEBUG=True`), emails are printed to the console instead of being sent. This allows testing without configuring an SMTP server.

**Production Mode:**

For production deployments, configure the following environment variables:

```bash
# Email backend (default: django.core.mail.backends.smtp.EmailBackend)
export EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"

# SMTP server configuration
export EMAIL_HOST="smtp.gmail.com"              # Your SMTP server hostname
export EMAIL_PORT="587"                         # SMTP port (587 for TLS, 465 for SSL)
export EMAIL_HOST_USER="your-email@gmail.com"   # SMTP username
export EMAIL_HOST_PASSWORD="your-app-password"  # SMTP password or app password
export EMAIL_USE_TLS="True"                     # Use TLS encryption (recommended)
export EMAIL_USE_SSL="False"                    # Use SSL encryption (alternative to TLS)

# From email address
export DEFAULT_FROM_EMAIL="noreply@bingosync.com"
```

**Common SMTP Providers:**

- **Gmail**: Use `smtp.gmail.com:587` with TLS. You'll need to create an [App Password](https://support.google.com/accounts/answer/185833).
- **SendGrid**: Use `smtp.sendgrid.net:587` with your API key as the password.
- **Amazon SES**: Use your region-specific SMTP endpoint (e.g., `email-smtp.us-east-1.amazonaws.com:587`).
- **Mailgun**: Use `smtp.mailgun.org:587` with your Mailgun credentials.

**Password Reset Token Expiry:**

Password reset tokens expire after 24 hours for security. This is configured via the `PASSWORD_RESET_TIMEOUT` setting (default: 86400 seconds).

**Testing Email Configuration:**

You can test your email configuration using Django's shell:

```bash
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'This is a test email', 'from@example.com', ['to@example.com'])
```
