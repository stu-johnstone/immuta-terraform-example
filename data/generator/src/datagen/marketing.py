"""Marketing data for a company: web analytics in the style of Google
Analytics 4, campaigns, ad spend, leads, email and consent. One BigQuery
dataset per company, all with the same structure."""

from __future__ import annotations

import json
from decimal import Decimal

from . import fake
from .common import Company, country_sql, meta_columns, region_sql
from .model import At, Col, DaysAgo, Derived, Schema, Script, Sql, Table

CHANNELS = {"SEARCH": ("google", "cpc"), "SOCIAL": ("facebook", "paid_social"), "PROFESSIONAL_SOCIAL": ("linkedin", "paid_social"),
            "DISPLAY": ("display_network", "display"), "EMAIL": ("newsletter", "email"), "VIDEO": ("youtube", "video")}
UNPAID_SOURCES = {("google", "organic"): 30, ("(direct)", "(none)"): 25, ("partner_site", "referral"): 8}
VISITOR_COUNTRIES = {"AU": 78, "NZ": 8, "SG": 6, "GB": 5, "US": 3}
LEAD_MESSAGES = (
    "Hi, I would like to know more about {product}. Best time to call is after 5pm on {phone}.",
    "Please call me back about {product}. My email is {email} if that is easier.",
    "Comparing options for {product} at the moment, can someone send me your current rates?",
    "I am an existing customer and want to talk about {product}. I live in {suburb}.",
    "We are moving to {suburb} next month and need {product} sorted before then.",
    "Not happy with my current provider, looking to switch {product}. Call {phone}.",
)


def bronze(company: Company) -> list[Table]:
    meta = ("GA4_EXPORT", "ga4-daily")
    products = dict(company.products)

    r = fake.rng(company.key, "marketing", "campaigns")
    campaigns = []
    for i in range(20):
        channel = list(CHANNELS)[i % len(CHANNELS)]
        product = company.products[(i + i // len(CHANNELS)) % len(company.products)][0]
        end = r.randint(-30, 20)
        campaigns.append((
            f"CMP{i + 1:03d}", f"{products[product]} - {channel.replace('_', ' ').title()} - Wave {i // len(CHANNELS) + 1}",
            channel, product, DaysAgo(end + r.randint(30, 60)), DaysAgo(end),
            Decimal(r.randint(10, 120) * 1000), fake.weighted(r, {"APAC": 70, "EMEA": 10, "AMER": 5, "ALL": 15}), *meta,
        ))

    r = fake.rng(company.key, "marketing", "ad_spend")
    spend = []
    for c in campaigns:
        for day in range(30):
            impressions = r.randint(800, 25000)
            clicks = int(impressions * fake.rate(r, 0.005, 0.04, 3))
            spend.append((c[0], DaysAgo(day), impressions, clicks, fake.money(r, 40, 1200), *meta))

    r = fake.rng(company.key, "marketing", "sessions")
    sessions = []
    for i in range(480):
        campaign = r.choice(campaigns) if fake.chance(r, 0.55) else None
        source, medium = CHANNELS[campaign[2]] if campaign else fake.weighted(r, {f"{s}|{m}": w for (s, m), w in UNPAID_SOURCES.items()}).split("|")
        country = fake.weighted(r, VISITOR_COUNTRIES)
        city = r.choice(fake.PLACES[country])[0]
        page, page_product = r.choice(company.landing_pages)
        if campaign:
            page, page_product = next((p for p in company.landing_pages if p[1] == campaign[3]), (page, page_product))
        sessions.append({
            "id": f"SES{i + 1:06d}", "user": f"{r.randint(10**9, 10**10 - 1)}.{r.randint(10**9, 10**10 - 1)}",
            "at": At(fake.days_back(r, 0, 59), fake.minute_of_day(r, 6, 23)), "page": page, "product": page_product,
            "source": source, "medium": medium, "campaign": campaign[0] if campaign else None, "country": country,
            "city": city, "device": fake.weighted(r, {"mobile": 62, "desktop": 33, "tablet": 5}),
            "browser": fake.weighted(r, {"Chrome": 55, "Safari": 35, "Edge": 7, "Firefox": 3}),
            "ip": fake.ip_address(r), "pageviews": r.randint(1, 12),
        })
    session_rows = [
        (s["id"], s["user"], s["at"], s["page"], s["source"], s["medium"], s["campaign"], s["device"], s["browser"],
         r.choice({"AU": ("AU", "Australia"), "NZ": ("New Zealand",), "SG": ("Singapore",), "GB": ("United Kingdom",), "US": ("United States",)}[s["country"]]),
         s["city"], s["ip"], s["pageviews"] > 1, s["pageviews"], *meta)
        for s in sessions
    ]

    r = fake.rng(company.key, "marketing", "events")
    events, form_submits = [], []
    funnel = (("calculator_used", 0.2), ("form_start", 0.4), ("form_submit", 0.25), ("apply_start", 0.15), ("apply_complete", 0.08))
    for s in sessions:
        steps = ["page_view"] + [name for name, p in funnel if fake.chance(r, p)]
        for step_number, event_name in enumerate(steps):
            at = At(s["at"].days_ago, min(s["at"].minute + step_number * r.randint(1, 4), 1439))
            params = {"product": s["product"], "page_title": products[s["product"]]}
            if event_name == "calculator_used":
                params["calculator_amount"] = r.randint(5, 150) * 10000
            if event_name.startswith("form"):
                params["form_name"] = "contact_me"
            if event_name == "apply_complete":
                params["application_value"] = r.randint(1, 80) * 5000
            events.append((f"EVT{len(events) + 1:07d}", s["id"], s["user"], at, event_name,
                           s["page"] if step_number == 0 else f"{s['page']}/{event_name.replace('_', '-')}",
                           json.dumps(params, separators=(",", ":")), *meta))
            if event_name == "form_submit":
                form_submits.append((s, at))

    r = fake.rng(company.key, "marketing", "leads")
    leads, people = [], []
    for i, (s, at) in enumerate(form_submits):
        first, last = fake.name(r)
        email = fake.email(r, first, last)
        phone = fake.phone(r, s["country"])
        suburb = r.choice(fake.PLACES[s["country"]])[1]
        message = r.choice(LEAD_MESSAGES).format(product=products[s["product"]].lower(), phone=phone, email=email, suburb=suburb)
        consent = fake.chance(r, 0.7)
        leads.append((f"LEAD{i + 1:05d}", s["id"], at, f" {first}" if fake.chance(r, 0.1) else first, last.upper() if fake.chance(r, 0.1) else last,
                      email.upper() if fake.chance(r, 0.1) else email, phone, s["country"], s["product"], message, consent, *meta))
        people.append((email, consent))

    r = fake.rng(company.key, "marketing", "email")
    email_campaigns = [c for c in campaigns if c[2] == "EMAIL"]
    for _ in range(150):
        first, last = fake.name(r)
        people.append((fake.email(r, first, last), fake.chance(r, 0.85)))
    sends = []
    for i in range(500):
        campaign = r.choice(email_campaigns)
        email, _ = r.choice(people)
        opened = fake.chance(r, 0.38)
        clicked = opened and fake.chance(r, 0.25)
        sends.append((f"SND{i + 1:06d}", campaign[0], email, At(fake.days_back(r, 0, 59), fake.minute_of_day(r, 6, 10)),
                      opened, clicked, fake.chance(r, 0.01), *meta))

    r = fake.rng(company.key, "marketing", "consents")
    consents = []
    for email, granted in people[:300]:
        consent_type = fake.weighted(r, {"EMAIL_MARKETING": 60, "SMS_MARKETING": 25, "PROFILING": 15})
        recorded = fake.days_back(r, 30, 700)
        source = fake.weighted(r, {"web_form": 60, "mobile_app": 25, "branch": 15})
        consents.append((email, consent_type, granted, At(recorded, fake.minute_of_day(r)), source))
        if granted and fake.chance(r, 0.08):
            consents.append((email, consent_type, False, At(fake.days_back(r, 0, recorded - 1), fake.minute_of_day(r)), "preference_centre"))
    consent_rows = [(f"CON{i + 1:06d}", *c, *meta) for i, c in enumerate(consents)]

    m = meta_columns()
    return [
        Table("bronze_campaigns", "Marketing campaigns from the campaign planning tool.", [
            Col("campaign_id", "string"), Col("campaign_name", "string"), Col("channel", "string"),
            Col("product_code", "string"), Col("start_date", "date"), Col("end_date", "date"),
            Col("budget_aud", "decimal(12,2)"), Col("target_region", "string"), *m], campaigns),
        Table("bronze_ad_spend", "Daily impressions, clicks and cost per campaign from the ad platforms.", [
            Col("campaign_id", "string"), Col("spend_date", "date"), Col("impressions", "int"), Col("clicks", "int"),
            Col("cost_aud", "decimal(12,2)"), *m], spend),
        Table("bronze_web_sessions", "Web sessions from the analytics export (GA4 style). Country spellings vary.", [
            Col("session_id", "string"), Col("user_pseudo_id", "string", "Pseudonymous device identifier"),
            Col("session_start", "timestamp"), Col("landing_page", "string"), Col("traffic_source", "string"),
            Col("traffic_medium", "string"), Col("campaign_id", "string"), Col("device_category", "string"),
            Col("browser", "string"), Col("country", "string"), Col("city", "string"),
            Col("ip_address", "string", "PII: IP address"), Col("is_engaged", "bool"), Col("pageviews", "int"), *m,
        ], session_rows),
        Table("bronze_web_events", "Web events from the analytics export. event_params is the raw JSON payload.", [
            Col("event_id", "string"), Col("session_id", "string"), Col("user_pseudo_id", "string", "Pseudonymous device identifier"),
            Col("event_ts", "timestamp"), Col("event_name", "string"), Col("page_path", "string"),
            Col("event_params", "json", "Raw JSON: product, page title, form, calculator and application amounts"), *m,
        ], events),
        Table("bronze_leads", "Contact-me form submissions from the web site. Names and emails are as typed.", [
            Col("lead_id", "string"), Col("session_id", "string"), Col("submitted_at", "timestamp"),
            Col("first_name", "string", "Person name"), Col("last_name", "string", "Person name"),
            Col("email", "string", "PII: email"), Col("phone", "string", "PII: phone number"), Col("country", "string"),
            Col("product_code", "string"), Col("message", "text", "Free text: often contains phone numbers, emails and suburbs"),
            Col("marketing_consent", "bool"), *m,
        ], leads),
        Table("bronze_email_sends", "Marketing emails sent, opened and clicked, from the email platform.", [
            Col("send_id", "string"), Col("campaign_id", "string"), Col("email", "string", "PII: email"),
            Col("sent_at", "timestamp"), Col("opened", "bool"), Col("clicked", "bool"), Col("unsubscribed", "bool"), *m,
        ], sends),
        Table("bronze_consents", "Marketing consent changes from the preference centre: one row per change.", [
            Col("consent_id", "string"), Col("email", "string", "PII: email"), Col("consent_type", "string"),
            Col("granted", "bool"), Col("recorded_at", "timestamp"), Col("capture_source", "string"), *m,
        ], consent_rows),
    ]


def silver() -> list[Derived]:
    def campaigns_sql(s: Sql) -> str:
        return f"""
SELECT campaign_id, campaign_name, channel, product_code, start_date, end_date, budget_aud, target_region
FROM {s.ref('bronze_campaigns')}"""

    def ad_spend_sql(s: Sql) -> str:
        return f"""
SELECT campaign_id, spend_date, impressions, clicks, cost_aud
FROM {s.ref('bronze_ad_spend')}"""

    def sessions_sql(s: Sql) -> str:
        return f"""
WITH base AS (
  SELECT
    session_id,
    user_pseudo_id,
    session_start,
    CAST(session_start AS DATE) AS session_date,
    landing_page,
    traffic_source,
    traffic_medium,
    campaign_id,
    device_category,
    browser,
    {country_sql('country')} AS country,
    city,
    ip_address,
    is_engaged,
    pageviews
  FROM {s.ref('bronze_web_sessions')}
)
SELECT base.*, {region_sql('base.country')} AS region
FROM base"""

    def events_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  e.event_id,
  e.session_id,
  e.user_pseudo_id,
  e.event_ts,
  CAST(e.event_ts AS DATE) AS event_date,
  e.event_name,
  e.page_path,
  {d.json_text('e.event_params', 'product')} AS product_code,
  {d.json_text('e.event_params', 'form_name')} AS form_name,
  CAST({d.json_text('e.event_params', 'calculator_amount')} AS {d.type('decimal(14,2)')}) AS calculator_amount,
  CAST({d.json_text('e.event_params', 'application_value')} AS {d.type('decimal(14,2)')}) AS application_value,
  s.campaign_id,
  s.traffic_source,
  s.traffic_medium,
  s.country,
  s.region
FROM {s.ref('bronze_web_events')} e
JOIN {s.ref('silver_web_sessions')} s ON s.session_id = e.session_id"""

    def leads_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  l.lead_id,
  l.session_id,
  l.submitted_at,
  CAST(l.submitted_at AS DATE) AS submitted_date,
  {d.initcap('TRIM(l.first_name)')} AS first_name,
  {d.initcap('TRIM(l.last_name)')} AS last_name,
  LOWER(TRIM(l.email)) AS email,
  l.phone,
  l.product_code,
  l.message,
  l.marketing_consent,
  s.campaign_id,
  s.traffic_source,
  s.traffic_medium,
  s.country,
  s.region
FROM {s.ref('bronze_leads')} l
JOIN {s.ref('silver_web_sessions')} s ON s.session_id = l.session_id"""

    def email_sql(s: Sql) -> str:
        return f"""
SELECT
  e.send_id,
  e.campaign_id,
  c.campaign_name,
  c.product_code,
  LOWER(e.email) AS email,
  e.sent_at,
  CAST(e.sent_at AS DATE) AS sent_date,
  e.opened,
  e.clicked,
  e.unsubscribed
FROM {s.ref('bronze_email_sends')} e
LEFT JOIN {s.ref('silver_campaigns')} c ON c.campaign_id = e.campaign_id"""

    def consents_sql(s: Sql) -> str:
        return f"""
WITH ranked AS (
  SELECT c.*, ROW_NUMBER() OVER (PARTITION BY LOWER(c.email), c.consent_type ORDER BY c.recorded_at DESC) AS rn
  FROM {s.ref('bronze_consents')} c
)
SELECT
  consent_id,
  LOWER(email) AS email,
  consent_type,
  granted,
  recorded_at,
  capture_source,
  CASE WHEN rn = 1 THEN TRUE ELSE FALSE END AS is_current
FROM ranked"""

    return [
        Derived("silver_campaigns", "Campaigns.", campaigns_sql),
        Derived("silver_ad_spend", "Daily ad spend per campaign.", ad_spend_sql),
        Derived("silver_web_sessions", "Web sessions with clean country codes, region and session date.", sessions_sql),
        Derived("silver_web_events", "Web events with the JSON parameters parsed into columns, and session attribution.", events_sql),
        Derived("silver_leads", "Leads with tidied names and emails, campaign attribution and region.", leads_sql),
        Derived("silver_email_sends", "Email sends with campaign and product.", email_sql),
        Derived("silver_consents", "Consent history; is_current marks the latest choice per email and consent type.", consents_sql),
    ]


def gold() -> list[Derived]:
    def campaign_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH spend AS (
  SELECT campaign_id, SUM(impressions) AS impressions, SUM(clicks) AS clicks, SUM(cost_aud) AS cost_aud
  FROM {s.ref('silver_ad_spend')}
  GROUP BY campaign_id
),
sessions AS (
  SELECT campaign_id, COUNT(*) AS sessions FROM {s.ref('silver_web_sessions')} GROUP BY campaign_id
),
leads AS (
  SELECT campaign_id, COUNT(*) AS leads FROM {s.ref('silver_leads')} GROUP BY campaign_id
),
applications AS (
  SELECT campaign_id, COUNT(*) AS applications, SUM(application_value) AS application_value
  FROM {s.ref('silver_web_events')}
  WHERE event_name = 'apply_complete'
  GROUP BY campaign_id
)
SELECT
  c.campaign_id,
  c.campaign_name,
  c.channel,
  c.product_code,
  c.target_region,
  c.start_date,
  c.end_date,
  c.budget_aud,
  COALESCE(sp.cost_aud, 0) AS spend_aud,
  COALESCE(sp.impressions, 0) AS impressions,
  COALESCE(sp.clicks, 0) AS clicks,
  {d.pct('sp.clicks', 'sp.impressions')} AS click_through_rate_pct,
  COALESCE(se.sessions, 0) AS sessions,
  COALESCE(l.leads, 0) AS leads,
  COALESCE(a.applications, 0) AS applications,
  COALESCE(a.application_value, 0) AS application_value_aud,
  {d.money('sp.cost_aud / NULLIF(l.leads, 0)')} AS cost_per_lead_aud,
  {d.money('sp.cost_aud / NULLIF(a.applications, 0)')} AS cost_per_application_aud
FROM {s.ref('silver_campaigns')} c
LEFT JOIN spend sp ON sp.campaign_id = c.campaign_id
LEFT JOIN sessions se ON se.campaign_id = c.campaign_id
LEFT JOIN leads l ON l.campaign_id = c.campaign_id
LEFT JOIN applications a ON a.campaign_id = c.campaign_id"""

    def funnel_sql(s: Sql) -> str:
        return f"""
SELECT
  event_date,
  product_code,
  region,
  COUNT(DISTINCT session_id) AS sessions,
  SUM(CASE WHEN event_name = 'calculator_used' THEN 1 ELSE 0 END) AS calculator_uses,
  SUM(CASE WHEN event_name = 'form_start' THEN 1 ELSE 0 END) AS form_starts,
  SUM(CASE WHEN event_name = 'form_submit' THEN 1 ELSE 0 END) AS form_submits,
  SUM(CASE WHEN event_name = 'apply_start' THEN 1 ELSE 0 END) AS application_starts,
  SUM(CASE WHEN event_name = 'apply_complete' THEN 1 ELSE 0 END) AS applications_completed
FROM {s.ref('silver_web_events')}
GROUP BY 1, 2, 3"""

    def channel_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH conversions AS (
  SELECT session_id, MAX(CASE WHEN event_name = 'apply_complete' THEN 1 ELSE 0 END) AS converted
  FROM {s.ref('silver_web_events')}
  GROUP BY session_id
),
leads AS (
  SELECT session_id, COUNT(*) AS leads FROM {s.ref('silver_leads')} GROUP BY session_id
)
SELECT
  ws.traffic_source,
  ws.traffic_medium,
  ws.region,
  COUNT(*) AS sessions,
  SUM(CASE WHEN ws.is_engaged THEN 1 ELSE 0 END) AS engaged_sessions,
  SUM(COALESCE(l.leads, 0)) AS leads,
  SUM(COALESCE(c.converted, 0)) AS applications,
  {d.pct('SUM(COALESCE(c.converted, 0))', 'COUNT(*)')} AS conversion_rate_pct
FROM {s.ref('silver_web_sessions')} ws
LEFT JOIN conversions c ON c.session_id = ws.session_id
LEFT JOIN leads l ON l.session_id = ws.session_id
GROUP BY 1, 2, 3"""

    return [
        Derived("gold_campaign_performance", "Spend, reach, leads, applications and cost per lead and application, per campaign.", campaign_sql),
        Derived("gold_funnel_daily", "Daily web funnel by product and region: sessions, calculator uses, forms and applications.", funnel_sql),
        Derived("gold_channel_performance", "Sessions, leads, applications and conversion rate by traffic source, medium and region.", channel_sql),
    ]


def script(company: Company) -> Script:
    return Script(
        path=f"{company.folder}/bigquery/{company.key}_marketing.sql",
        title=f"{company.name} - Marketing",
        description=(
            f"Marketing data for {company.name}: web analytics in the style of Google Analytics 4, "
            "campaigns, ad spend, leads, email and consent. Every company's marketing data has the "
            "same structure, in its own dataset."
        ),
        platform="bigquery",
        container=None,
        schemas=[Schema(f"{company.key}_marketing", f"{company.name} Marketing",
                        f"Marketing and web analytics data for {company.name}.", bronze(company), silver(), gold())],
    )
