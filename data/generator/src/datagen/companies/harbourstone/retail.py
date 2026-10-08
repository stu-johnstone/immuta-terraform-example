"""Retail banking: customers, KYC, accounts, transactions, cards, home
loans, CRM, complaints and AML alerts."""

from __future__ import annotations

from decimal import Decimal

from ... import fake, hr
from ...common import aud_sql, country_sql, meta_columns, region_sql
from ...model import At, Col, DaysAgo, Derived, Schema, Sql, Table
from . import COMPANY

BRANCHES = (
    ("BR001", "Sydney CBD", "AU", "Sydney", "NSW", "2000"), ("BR002", "Parramatta", "AU", "Parramatta", "NSW", "2150"),
    ("BR003", "Chatswood", "AU", "Chatswood", "NSW", "2067"), ("BR004", "Newcastle", "AU", "Newcastle", "NSW", "2300"),
    ("BR005", "Melbourne CBD", "AU", "Melbourne", "VIC", "3000"), ("BR006", "Richmond", "AU", "Richmond", "VIC", "3121"),
    ("BR007", "Geelong", "AU", "Geelong", "VIC", "3220"), ("BR008", "Brisbane CBD", "AU", "Brisbane", "QLD", "4000"),
    ("BR009", "Gold Coast", "AU", "Southport", "QLD", "4215"), ("BR010", "Perth CBD", "AU", "Perth", "WA", "6000"),
    ("BR011", "Fremantle", "AU", "Fremantle", "WA", "6160"), ("BR012", "Adelaide", "AU", "Adelaide", "SA", "5000"),
    ("BR013", "Hobart", "AU", "Hobart", "TAS", "7000"), ("BR014", "Canberra", "AU", "Braddon", "ACT", "2612"),
    ("BR015", "Auckland", "NZ", "Ponsonby", "AUK", "1011"), ("BR016", "Singapore", "SG", "Tanjong Pagar", "SG", "088539"),
    ("BR017", "London", "GB", "Canary Wharf", "LND", "E14 5AB"), ("BR900", "Digital Banking", "AU", "Sydney", "NSW", "2000"),
)
CUSTOMER_COUNTRIES = {"AU": 74, "NZ": 9, "SG": 7, "GB": 6, "US": 4}
RAW_COUNTRY = {"AU": ("AU", "AU", "AU", "Australia", "AUS", "au "), "NZ": ("NZ", "New Zealand"), "SG": ("SG", "Singapore"),
               "GB": ("GB", "UK", "United Kingdom"), "US": ("US", "USA")}
MERCHANTS = ("Corner Grocer", "Bean There Cafe", "Metro Fuel", "City Pharmacy", "Harbour Fish Market", "Sunset Bottle Shop",
             "Gridlock Parking", "Pixel Electronics", "Green Leaf Grocers", "Northside Hardware", "Tram Stop Bakery",
             "Bluegum Books", "Swift Rideshare", "Stream Box Subscriptions", "Coastal Airlines")
EMPLOYERS = ("Bluegum Construction", "Harbour View Hospitality", "Southern Cross Logistics", "Wattle Health",
             "State Government", "Coastline Schools", "Ironbark Mining Services", "Kookaburra Software")
CRM_NOTES = {
    "Card lost or stolen": ("NEGATIVE", "Customer called to report card ending {last4} lost in {suburb}. Card blocked and replacement sent to {address}. Identity verified with date of birth {dob}."),
    "Fee query": ("NEUTRAL", "Customer queried a monthly account fee of {fee} dollars. Explained the fee waiver criteria and refunded it as a one-off courtesy."),
    "Home loan rate review": ("NEUTRAL", "Customer asked for a rate review on their home loan and mentioned a competitor offer of {rate} percent. Referred to the retention team."),
    "Hardship request": ("NEGATIVE", "Customer advised of reduced income after losing their job and asked for hardship assistance. Partner {partner} is also on the account. Three month repayment pause logged."),
    "Address change": ("POSITIVE", "Customer moved to {address}. Records updated after verifying mobile {phone}."),
    "Fraud concern": ("NEGATIVE", "Customer reported a text message asking for their online banking password. Advised not to respond. No transactions affected."),
    "Term deposit maturity": ("POSITIVE", "Term deposit maturing next week. Customer wants to roll over {fee}00 dollars for 12 months."),
    "Online banking access": ("NEUTRAL", "Customer locked out of online banking. Password reset after verification by SMS to {phone}."),
    "Complaint follow-up": ("NEGATIVE", "Called customer about their open complaint. Customer is still unhappy with the outcome and may escalate to the ombudsman."),
    "Product enquiry": ("POSITIVE", "Customer asked about a credit card with travel insurance. Product information sent to {email}."),
}
COMPLAINTS = {
    "FEES": "I was charged {amount} dollars in overdrawn fees in one week. Nobody told me about these fees and I want them refunded.",
    "SERVICE": "I waited over an hour on the phone and was transferred three times. Nobody could tell me why my transfer was delayed.",
    "HARDSHIP": "I asked for help after losing my job but my hardship application has not been answered for {days} days.",
    "FRAUD": "There are card transactions at {merchant} that I did not make. It took two weeks to get my money back.",
    "LENDING": "My home loan application was declined without a clear reason after I provided everything that was asked for.",
    "DIGITAL": "The mobile app keeps logging me out and I could not pay my rent on time.",
    "PRIVACY": "A letter with my account details was sent to my old address at {address} even though I updated it months ago.",
}
AML_NOTES = {
    "STRUCTURING": "Three cash deposits just under 10,000 dollars at {branch} within a week. Pattern consistent with structuring to avoid threshold reporting.",
    "HIGH_RISK_COUNTRY": "Outbound transfer to a beneficiary in a high-risk jurisdiction. Customer states it is support for family overseas. Source of funds requested.",
    "RAPID_MOVEMENT": "Funds received and transferred out within 24 hours, several times this month. Possible mule account activity.",
    "LARGE_CASH": "Single large cash deposit inconsistent with declared income from {employer}.",
}

_customers: list[dict] | None = None


def customers() -> list[dict]:
    """Retail customers. Also used by insurance, as some are policyholders."""
    global _customers
    if _customers is not None:
        return _customers
    r = fake.rng("harbourstone", "retail", "customers")
    result = []
    for i in range(250):
        country = fake.weighted(r, CUSTOMER_COUNTRIES)
        first, last = fake.name(r)
        local = [b for b in BRANCHES if b[2] == country and b[0] != "BR900"]
        branch = r.choice(local)[0] if local and fake.chance(r, 0.85) else "BR900"
        result.append({
            "id": f"C{100001 + i}", "first": first, "last": last, "country": country, "branch": branch,
            "dob": fake.birth_date(r, 18, 88), "email": fake.email(r, first, last), "phone": fake.phone(r, country),
            "address": fake.address(r, country), "since": r.randint(30, 365 * 25),
            "segment": fake.weighted(r, {"MASS": 70, "AFFLUENT": 22, "PRIVATE": 8}),
        })
    _customers = result
    return result


def bronze() -> list[Table]:
    people = customers()
    m = meta_columns()
    branch_name = {b[0]: b[1] for b in BRANCHES}

    branch_rows = [(b[0], b[1], b[3], b[4], b[5], b[2], DaysAgo(365 * 5 + i * 97), "CBS", "cbs-ref") for i, b in enumerate(BRANCHES)]

    r = fake.rng("harbourstone", "retail", "customer_rows")
    customer_rows = []
    for c in people:
        customer_rows.append((
            c["id"], c["first"].upper() if fake.chance(r, 0.08) else c["first"], c["last"], c["dob"],
            fake.weighted(r, {"F": 50, "M": 48, "X": 2}), c["email"].upper() if fake.chance(r, 0.05) else c["email"],
            c["phone"], fake.tfn(r) if c["country"] == "AU" and fake.chance(r, 0.9) else None, c["branch"],
            DaysAgo(c["since"]), r.choice(RAW_COUNTRY[c["country"]]), c["segment"],
            r.choice(("Active", "ACTIVE", "active ", "Active")) if fake.chance(r, 0.93) else r.choice(("Dormant", "Deceased")),
            "CBS", "cbs-0412",
        ))

    r = fake.rng("harbourstone", "retail", "addresses")
    address_rows = []
    for c in people:
        a = c["address"]
        moved = r.randint(30, c["since"]) if c["since"] > 60 and fake.chance(r, 0.25) else None
        address_rows.append((c["id"], "RESIDENTIAL", a["address_line"], a["suburb"], a["state"], a["postcode"], c["country"],
                             DaysAgo(moved or c["since"]), None))
        if moved:
            old = fake.address(r, c["country"])
            address_rows.append((c["id"], "RESIDENTIAL", old["address_line"], old["suburb"], old["state"], old["postcode"],
                                 c["country"], DaysAgo(c["since"]), DaysAgo(moved)))
        if fake.chance(r, 0.1):
            address_rows.append((c["id"], "POSTAL", f"PO Box {r.randint(100, 9999)}", a["suburb"], a["state"], a["postcode"],
                                 c["country"], DaysAgo(c["since"]), None))
    address_rows = [(f"ADR{i:06d}", *row, "CBS", "cbs-0412") for i, row in enumerate(address_rows, start=1)]

    r = fake.rng("harbourstone", "retail", "kyc")
    kyc_rows = []
    for c in people:
        doc_types = ["DRIVERS_LICENCE" if c["country"] == "AU" and fake.chance(r, 0.6) else "PASSPORT"]
        if fake.chance(r, 0.2):
            doc_types.append("PASSPORT" if doc_types[0] == "DRIVERS_LICENCE" else "MEDICARE_CARD" if c["country"] == "AU" else "NATIONAL_ID")
        for doc_type in doc_types:
            number = {"PASSPORT": fake.passport(r, c["country"]), "DRIVERS_LICENCE": fake.drivers_licence(r),
                      "MEDICARE_CARD": f"{r.randint(2, 6)}{fake.digits(r, 9)}", "NATIONAL_ID": fake.digits(r, 9)}[doc_type]
            kyc_rows.append((f"KYC{len(kyc_rows) + 1:06d}", c["id"], doc_type, number, c["country"],
                             DaysAgo(r.randint(-3000, 200)), At(min(c["since"], r.randint(1, 900)), fake.minute_of_day(r)),
                             fake.weighted(r, {"VERIFIED": 92, "PENDING": 5, "FAILED": 3}), "KYC_VENDOR", "kyc-0412"))

    r = fake.rng("harbourstone", "retail", "accounts")
    accounts = []
    for c in people:
        scale = {"MASS": 1, "AFFLUENT": 4, "PRIVATE": 15}[c["segment"]]
        products = ["TXN"] + (["SAV"] if fake.chance(r, 0.65) else []) + (["TD"] if fake.chance(r, 0.2) else [])
        for product in products:
            low, high = {"TXN": (20, 9000), "SAV": (200, 60000), "TD": (5000, 150000)}[product]
            status = fake.weighted(r, {"ACTIVE": 92, "DORMANT": 5, "CLOSED": 3})
            opened = r.randint(10, c["since"])
            accounts.append({
                "id": f"A{2000001 + len(accounts)}", "customer": c, "product": product, "status": status,
                "currency": fake.CURRENCIES[c["country"]], "balance": fake.money(r, low * scale, high * scale) if status != "CLOSED" else Decimal("0.00"),
                "opened": opened, "closed": r.randint(1, opened - 1) if status == "CLOSED" and opened > 1 else None,
                "rate": {"TXN": Decimal("0.00"), "SAV": fake.rate(r, 3.5, 5.2), "TD": fake.rate(r, 4.1, 5.0)}[product],
                "bsb": fake.bsb(r, COMPANY.bsb_prefix) if c["country"] == "AU" else None,
                "number": fake.digits(r, 9),
                "iban": fake.gb_iban(r, "HRBS") if c["country"] == "GB" else None,
            })
    account_rows = [
        (a["id"], a["customer"]["id"], a["product"], a["bsb"], a["number"], a["iban"], a["currency"], a["balance"], a["rate"],
         DaysAgo(a["opened"]), DaysAgo(a["closed"]) if a["closed"] else None, a["status"], "CBS", "cbs-0412")
        for a in accounts
    ]

    r = fake.rng("harbourstone", "retail", "transactions")
    open_accounts = [a for a in accounts if a["status"] == "ACTIVE" and a["product"] in ("TXN", "SAV")]
    transactions = []

    def add_txn(account, txn_type, amount, channel, description, days_ago, minute, merchant=None):
        transactions.append([f"T{90000001 + len(transactions)}", account["id"], At(days_ago, minute), txn_type, amount,
                             account["currency"], channel, merchant, description, "CBS", "cbs-0412"])

    structuring = r.sample([a for a in open_accounts if a["product"] == "TXN"], 12)
    for account in structuring:
        start = r.randint(3, 60)
        branch = branch_name[account["customer"]["branch"]]
        for k in range(3):
            add_txn(account, "DEPOSIT", fake.money(r, 9000, 9900), "BRANCH", f"CASH DEPOSIT {branch.upper()}", start - k * 2, fake.minute_of_day(r, 9, 16))
    txn_weights = {"DEPOSIT": 25, "CARD_PURCHASE": 35, "WITHDRAWAL": 10, "TRANSFER_IN": 10, "TRANSFER_OUT": 12, "FEE": 3, "INTEREST": 5}
    while len(transactions) < 1000:
        account = r.choice(open_accounts)
        txn_type = fake.weighted(r, txn_weights)
        days_ago = 0 if fake.chance(r, 0.18) else r.randint(1, 120)
        minute = fake.minute_of_day(r, 0, 24)
        first, last = fake.name(r)
        if txn_type == "DEPOSIT":
            if fake.chance(r, 0.5):
                add_txn(account, txn_type, fake.money(r, 1800, 6500), "DIRECT_CREDIT", f"SALARY {r.choice(EMPLOYERS).upper()}", days_ago, minute)
            else:
                channel = fake.weighted(r, {"BRANCH": 40, "ATM": 30, "ONLINE": 30})
                add_txn(account, txn_type, fake.money(r, 50, 4000), channel, "CASH DEPOSIT" if channel != "ONLINE" else "DEPOSIT", days_ago, minute)
        elif txn_type == "CARD_PURCHASE":
            merchant = r.choice(MERCHANTS)
            add_txn(account, txn_type, fake.money(r, 4, 350), fake.weighted(r, {"EFTPOS": 60, "ONLINE": 40}), merchant.upper(), days_ago, minute, merchant)
        elif txn_type == "WITHDRAWAL":
            add_txn(account, txn_type, Decimal(r.randint(1, 40) * 20), fake.weighted(r, {"ATM": 85, "BRANCH": 15}), "ATM WITHDRAWAL", days_ago, minute)
        elif txn_type == "TRANSFER_IN":
            add_txn(account, txn_type, fake.money(r, 20, 3000), "MOBILE", f"TRANSFER FROM {first[0]} {last.upper()}", days_ago, minute)
        elif txn_type == "TRANSFER_OUT":
            add_txn(account, txn_type, fake.money(r, 20, 3000), fake.weighted(r, {"MOBILE": 70, "ONLINE": 30}), f"TRANSFER TO {first[0]} {last.upper()}", days_ago, minute)
        elif txn_type == "FEE":
            add_txn(account, txn_type, r.choice((Decimal("5.00"), Decimal("15.00"), Decimal("2.50"))), "SYSTEM", r.choice(("MONTHLY ACCOUNT FEE", "OVERDRAWN FEE", "OVERSEAS TXN FEE")), days_ago, 1)
        else:
            add_txn(account, txn_type, fake.money(r, 0.5, 120), "SYSTEM", "CREDIT INTEREST", days_ago, 2)
    # The core banking extract re-sends some transactions; silver removes the duplicates.
    duplicates = [list(t) for t in r.sample(transactions, 10)]
    for t in duplicates:
        t[-1] = "cbs-0413"
    transaction_rows = [tuple(t) for t in transactions + duplicates]

    r = fake.rng("harbourstone", "retail", "cards")
    card_rows, card_last4 = [], {}
    credit_holders = set(c["id"] for c in r.sample(people, 70))
    for a in accounts:
        if a["product"] != "TXN":
            continue
        c = a["customer"]
        kinds = (["DEBIT"] if fake.chance(r, 0.85) else []) + (["CREDIT"] if c["id"] in credit_holders else [])
        for kind in kinds:
            number = fake.card_number(r)
            card_last4.setdefault(c["id"], number[-4:])
            card_rows.append((f"CRD{len(card_rows) + 1:06d}", a["id"], number, f"{c['first'][0]} {c['last']}".upper(), kind,
                              Decimal(r.randint(4, 60) * 500) if kind == "CREDIT" else None,
                              f"{r.randint(1, 12):02d}/{r.randint(27, 31)}", fake.weighted(r, {"ACTIVE": 90, "BLOCKED": 4, "LOST_STOLEN": 6}),
                              DaysAgo(r.randint(10, min(a["opened"], 1500) + 10)), "CARDS", "cards-0412"))

    r = fake.rng("harbourstone", "retail", "home_loans")
    loan_rows = []
    borrowers = r.sample([c for c in people if c["country"] in ("AU", "NZ")], 100)
    for c in borrowers:
        value = Decimal(r.randint(45, 260) * 10000)
        loan = (value * fake.rate(r, 0.55, 0.92)).quantize(Decimal("1"))
        start = r.randint(60, 365 * 12)
        balance = (loan * (1 - Decimal(start) / Decimal(365 * 40))).quantize(Decimal("0.01"))
        arrears = 0 if fake.chance(r, 0.86) else r.choice((5, 12, 25, 40, 75, 95, 130))
        loan_rows.append((f"HL{len(loan_rows) + 1:05d}", c["id"], c["address"]["postcode"], value, loan, balance,
                          fake.rate(r, 5.6, 7.2), fake.weighted(r, {"VARIABLE": 70, "FIXED": 30}), r.choice((25, 30)),
                          DaysAgo(start), arrears, "LENDING", "lending-0412"))

    r = fake.rng("harbourstone", "retail", "crm")
    retail_staff = hr.staff_in(COMPANY, "RETAIL_BANKING")
    crm_rows = []
    for i in range(300):
        c = r.choice(people)
        topic = r.choice(list(CRM_NOTES))
        sentiment, template = CRM_NOTES[topic]
        partner_first, _ = fake.name(r)
        a = c["address"]
        notes = template.format(
            last4=card_last4.get(c["id"], fake.digits(r, 4)), suburb=a["suburb"], dob=c["dob"].strftime("%d/%m/%Y"),
            address=f"{a['address_line']}, {a['suburb']} {a['state']} {a['postcode']}", fee=r.choice((5, 10, 15)),
            rate=fake.rate(r, 5.4, 6.1), partner=f"{partner_first} {c['last']}", phone=c["phone"], email=c["email"],
        )
        crm_rows.append((f"INT{i + 1:06d}", c["id"], At(r.randint(0, 180), fake.minute_of_day(r, 8, 20)),
                         fake.weighted(r, {"PHONE": 55, "BRANCH": 20, "CHAT": 15, "EMAIL": 10}), r.choice(retail_staff)["employee_id"],
                         topic, notes, sentiment, "CRM", "crm-0412"))

    r = fake.rng("harbourstone", "retail", "complaints")
    complaint_rows = []
    for i in range(110):
        c = r.choice(people)
        category = fake.weighted(r, {"FEES": 22, "SERVICE": 25, "HARDSHIP": 10, "FRAUD": 12, "LENDING": 10, "DIGITAL": 15, "PRIVACY": 6})
        a = c["address"]
        text = COMPLAINTS[category].format(amount=r.choice((45, 60, 90)), days=r.randint(20, 60), merchant=r.choice(MERCHANTS),
                                           address=f"{a['address_line']}, {a['suburb']}")
        received = r.randint(0, 365)
        status = "OPEN" if received < 7 else fake.weighted(r, {"RESOLVED": 70, "IN_PROGRESS": 18, "ESCALATED": 7, "OPEN": 5})
        resolved = DaysAgo(max(received - r.randint(1, 45), 0)) if status == "RESOLVED" else None
        compensation = Decimal(r.choice((25, 50, 100, 250, 500))) if status == "RESOLVED" and fake.chance(r, 0.4) else None
        complaint_rows.append((f"CMP{i + 1:05d}", c["id"], DaysAgo(received), category, text, status, resolved, compensation,
                               "CRM", "crm-0412"))

    r = fake.rng("harbourstone", "retail", "aml")
    aml_rows = []
    deposits_by_account = {}
    for t in transactions:
        if t[3] == "DEPOSIT" and t[6] == "BRANCH" and t[4] >= 9000:
            deposits_by_account[t[1]] = t
    account_by_id = {a["id"]: a for a in accounts}
    for account_id, t in deposits_by_account.items():
        a = account_by_id[account_id]
        aml_rows.append((a["customer"]["id"], t[0], "STRUCTURING", r.randint(70, 98),
                         AML_NOTES["STRUCTURING"].format(branch=branch_name[a["customer"]["branch"]]), t[2].days_ago))
    candidates = [t for t in transactions if t[3] in ("TRANSFER_OUT", "TRANSFER_IN", "DEPOSIT")]
    for t in r.sample(candidates, 68):
        rule = {"TRANSFER_OUT": "HIGH_RISK_COUNTRY", "TRANSFER_IN": "RAPID_MOVEMENT", "DEPOSIT": "LARGE_CASH"}[t[3]]
        a = account_by_id[t[1]]
        aml_rows.append((a["customer"]["id"], t[0], rule, r.randint(20, 90), AML_NOTES[rule].format(employer=r.choice(EMPLOYERS)), t[2].days_ago))
    aml_rows = [
        (f"AML{i:05d}", customer, txn, At(days_ago, fake.minute_of_day(r, 1, 5)), rule, score,
         "OPEN" if days_ago < 5 else fake.weighted(r, {"UNDER_REVIEW": 30, "CLOSED_FALSE_POSITIVE": 50, "REPORTED": 15, "OPEN": 5}),
         notes, "AML_ENGINE", "aml-0412")
        for i, (customer, txn, rule, score, notes, days_ago) in enumerate(aml_rows, start=1)
    ]

    return [
        Table("bronze_branches", "Branches from the core banking system. BR900 is the digital (online) branch.", [
            Col("branch_id", "string"), Col("branch_name", "string"), Col("suburb", "string"), Col("state", "string"),
            Col("postcode", "string"), Col("country", "string"), Col("opened_date", "date"), *m], branch_rows),
        Table("bronze_customers", "Retail customers from the core banking system. Raw values: name casing, status and country spellings vary.", [
            Col("customer_id", "string"), Col("first_name", "string", "Person name"), Col("last_name", "string", "Person name"),
            Col("date_of_birth", "date", "PII: date of birth"), Col("gender", "string", "Sensitive: gender"),
            Col("email", "string", "PII: email"), Col("mobile_phone", "string", "PII: phone number"),
            Col("tax_file_number", "string", "Highly sensitive: Australian tax file number (AU customers)"),
            Col("home_branch_id", "string"), Col("customer_since", "date"), Col("country", "string"),
            Col("segment", "string", "MASS, AFFLUENT or PRIVATE"), Col("customer_status", "string"), *m], customer_rows),
        Table("bronze_customer_addresses", "Customer address history; valid_to is empty for current addresses.", [
            Col("address_id", "string"), Col("customer_id", "string"), Col("address_type", "string"),
            Col("address_line", "string", "PII: street address"), Col("suburb", "string"), Col("state", "string"),
            Col("postcode", "string"), Col("country", "string"), Col("valid_from", "date"), Col("valid_to", "date"), *m], address_rows),
        Table("bronze_kyc_documents", "Identity documents checked when customers were onboarded, from the KYC vendor.", [
            Col("document_id", "string"), Col("customer_id", "string"), Col("document_type", "string"),
            Col("document_number", "string", "Highly sensitive: passport, licence, Medicare or national ID number"),
            Col("issuing_country", "string"), Col("expiry_date", "date"), Col("verified_at", "timestamp"),
            Col("verification_status", "string"), *m], kyc_rows),
        Table("bronze_accounts", "Deposit accounts (everyday, savings and term deposit) from the core banking system.", [
            Col("account_id", "string"), Col("customer_id", "string"), Col("product_code", "string", "TXN, SAV or TD"),
            Col("bsb", "string", "Financial: BSB (AU accounts)"), Col("account_number", "string", "Financial: account number"),
            Col("iban", "string", "Financial: IBAN (London accounts)"), Col("currency", "string"),
            Col("current_balance", "decimal(14,2)"), Col("interest_rate", "decimal(5,2)"), Col("opened_date", "date"),
            Col("closed_date", "date"), Col("account_status", "string"), *m], account_rows),
        Table("bronze_transactions", "Account transactions for the last 120 days, including today. The extract re-sends a few rows.", [
            Col("txn_id", "string"), Col("account_id", "string"), Col("txn_ts", "timestamp"), Col("txn_type", "string"),
            Col("amount", "decimal(14,2)", "Always positive; the type gives the direction"), Col("currency", "string"),
            Col("channel", "string"), Col("merchant_name", "string"), Col("description", "string"), *m], transaction_rows),
        Table("bronze_cards", "Debit and credit cards from the card management system.", [
            Col("card_id", "string"), Col("account_id", "string"),
            Col("card_number", "string", "PCI: full card number (test ranges, Luhn-valid)"),
            Col("cardholder_name", "string", "Person name"), Col("card_type", "string"), Col("credit_limit", "decimal(12,2)"),
            Col("expiry_month", "string", "PCI: MM/YY"), Col("card_status", "string"), Col("issued_date", "date"), *m], card_rows),
        Table("bronze_home_loans", "Home loans from the lending system.", [
            Col("loan_id", "string"), Col("customer_id", "string"), Col("property_postcode", "string"),
            Col("property_value", "decimal(14,2)"), Col("original_loan_amount", "decimal(14,2)"),
            Col("current_balance", "decimal(14,2)"), Col("interest_rate", "decimal(5,2)"), Col("rate_type", "string"),
            Col("term_years", "int"), Col("start_date", "date"), Col("days_in_arrears", "int"), *m], loan_rows),
        Table("bronze_crm_interactions", "Customer contacts logged in the CRM, with the staff member's notes.", [
            Col("interaction_id", "string"), Col("customer_id", "string"), Col("interaction_ts", "timestamp"),
            Col("channel", "string"), Col("staff_employee_id", "string", "Matches employee_id in the HR data"),
            Col("topic", "string"), Col("notes", "text", "Free text: often contains card digits, addresses, phone numbers and dates of birth"),
            Col("sentiment", "string"), *m], crm_rows),
        Table("bronze_complaints", "Customer complaints from the CRM, in the customer's words.", [
            Col("complaint_id", "string"), Col("customer_id", "string"), Col("received_date", "date"), Col("category", "string"),
            Col("description", "text", "Free text: the customer's complaint"), Col("complaint_status", "string"),
            Col("resolved_date", "date"), Col("compensation_amount", "decimal(10,2)"), *m], complaint_rows),
        Table("bronze_aml_alerts", "Anti-money laundering alerts raised by the transaction monitoring engine.", [
            Col("alert_id", "string"), Col("customer_id", "string"), Col("txn_id", "string"), Col("alert_ts", "timestamp"),
            Col("rule_code", "string"), Col("risk_score", "int", "0 to 100"), Col("alert_status", "string"),
            Col("analyst_notes", "text", "Free text: financial crime investigation notes"), *m], aml_rows),
    ]


def silver() -> list[Derived]:
    def branches_sql(s: Sql) -> str:
        return f"""
SELECT branch_id, branch_name, suburb, state, postcode, country, {region_sql('country')} AS region, opened_date
FROM {s.ref('bronze_branches')}"""

    def customers_sql(s: Sql) -> str:
        d = s.d
        return f"""
WITH current_address AS (
  SELECT customer_id, address_line, suburb, state, postcode
  FROM {s.ref('bronze_customer_addresses')}
  WHERE address_type = 'RESIDENTIAL' AND valid_to IS NULL
),
base AS (
  SELECT
    c.customer_id,
    {d.initcap('TRIM(c.first_name)')} AS first_name,
    {d.initcap('TRIM(c.last_name)')} AS last_name,
    c.date_of_birth,
    {d.age('c.date_of_birth')} AS age,
    c.gender,
    LOWER(TRIM(c.email)) AS email,
    c.mobile_phone,
    REGEXP_REPLACE(c.tax_file_number, '[^0-9]', '') AS tax_file_number,
    a.address_line,
    a.suburb,
    a.state,
    a.postcode,
    {country_sql('c.country')} AS country,
    c.home_branch_id,
    b.branch_name AS home_branch_name,
    c.segment,
    UPPER(TRIM(c.customer_status)) AS customer_status,
    c.customer_since
  FROM {s.ref('bronze_customers')} c
  LEFT JOIN current_address a ON a.customer_id = c.customer_id
  LEFT JOIN {s.ref('silver_branches')} b ON b.branch_id = c.home_branch_id
)
SELECT
  base.*,
  CASE WHEN age < 25 THEN '18-24' WHEN age < 35 THEN '25-34' WHEN age < 50 THEN '35-49' WHEN age < 65 THEN '50-64' ELSE '65+' END AS age_band,
  {region_sql('base.country')} AS region
FROM base"""

    def kyc_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  k.document_id,
  k.customer_id,
  k.document_type,
  k.document_number,
  k.issuing_country,
  k.expiry_date,
  CASE WHEN k.expiry_date < {d.today} THEN TRUE ELSE FALSE END AS is_expired,
  k.verified_at,
  k.verification_status,
  c.country,
  c.region
FROM {s.ref('bronze_kyc_documents')} k
JOIN {s.ref('silver_customers')} c ON c.customer_id = k.customer_id"""

    def accounts_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  a.account_id,
  a.customer_id,
  a.product_code,
  CASE a.product_code WHEN 'TXN' THEN 'Everyday Account' WHEN 'SAV' THEN 'Bonus Saver' WHEN 'TD' THEN 'Term Deposit' END AS product_name,
  a.bsb,
  a.account_number,
  a.iban,
  a.currency,
  a.current_balance,
  {aud_sql('a.current_balance', 'a.currency', d.money)} AS current_balance_aud,
  a.interest_rate,
  a.opened_date,
  a.closed_date,
  a.account_status,
  c.home_branch_id AS branch_id,
  c.country,
  c.region
FROM {s.ref('bronze_accounts')} a
JOIN {s.ref('silver_customers')} c ON c.customer_id = a.customer_id"""

    def transactions_sql(s: Sql) -> str:
        d = s.d
        credit = "t.txn_type IN ('DEPOSIT', 'TRANSFER_IN', 'INTEREST')"
        return f"""
WITH deduplicated AS (
  -- The extract re-sends some transactions: keep the latest copy of each.
  SELECT t.*, ROW_NUMBER() OVER (PARTITION BY t.txn_id ORDER BY t._batch_id DESC) AS rn
  FROM {s.ref('bronze_transactions')} t
)
SELECT
  t.txn_id,
  t.account_id,
  a.customer_id,
  t.txn_ts,
  CAST(t.txn_ts AS DATE) AS txn_date,
  t.txn_type,
  CASE WHEN {credit} THEN 'CREDIT' ELSE 'DEBIT' END AS direction,
  t.amount,
  CASE WHEN {credit} THEN t.amount ELSE -t.amount END AS signed_amount,
  t.currency,
  {aud_sql('t.amount', 't.currency', d.money)} AS amount_aud,
  t.channel,
  t.merchant_name,
  TRIM(t.description) AS description,
  a.product_code,
  a.branch_id,
  a.country,
  a.region
FROM deduplicated t
JOIN {s.ref('silver_accounts')} a ON a.account_id = t.account_id
WHERE t.rn = 1"""

    def cards_sql(s: Sql) -> str:
        return f"""
SELECT
  k.card_id,
  k.account_id,
  a.customer_id,
  k.card_number,
  k.cardholder_name,
  k.card_type,
  k.credit_limit,
  k.expiry_month,
  k.card_status,
  k.issued_date,
  a.country,
  a.region
FROM {s.ref('bronze_cards')} k
JOIN {s.ref('silver_accounts')} a ON a.account_id = k.account_id"""

    def home_loans_sql(s: Sql) -> str:
        return f"""
SELECT
  l.loan_id,
  l.customer_id,
  l.property_postcode,
  c.state,
  l.property_value,
  l.original_loan_amount,
  l.current_balance,
  ROUND(l.current_balance * 100 / l.property_value, 1) AS loan_to_value_pct,
  l.interest_rate,
  l.rate_type,
  l.term_years,
  l.start_date,
  l.days_in_arrears,
  CASE WHEN l.days_in_arrears = 0 THEN 'CURRENT' WHEN l.days_in_arrears <= 30 THEN '1-30 DAYS'
       WHEN l.days_in_arrears <= 90 THEN '31-90 DAYS' ELSE '90+ DAYS' END AS arrears_bucket,
  c.country,
  c.region
FROM {s.ref('bronze_home_loans')} l
JOIN {s.ref('silver_customers')} c ON c.customer_id = l.customer_id"""

    def crm_sql(s: Sql) -> str:
        return f"""
SELECT
  i.interaction_id,
  i.customer_id,
  i.interaction_ts,
  CAST(i.interaction_ts AS DATE) AS interaction_date,
  i.channel,
  i.staff_employee_id,
  i.topic,
  i.notes,
  i.sentiment,
  c.country,
  c.region
FROM {s.ref('bronze_crm_interactions')} i
JOIN {s.ref('silver_customers')} c ON c.customer_id = i.customer_id"""

    def complaints_sql(s: Sql) -> str:
        d = s.d
        return f"""
SELECT
  p.complaint_id,
  p.customer_id,
  p.received_date,
  {d.month_start('p.received_date')} AS received_month,
  p.category,
  p.description,
  p.complaint_status,
  p.resolved_date,
  {d.days_between('p.received_date', f'COALESCE(p.resolved_date, {d.today})')} AS days_open,
  COALESCE(p.compensation_amount, 0) AS compensation_amount,
  c.home_branch_id AS branch_id,
  c.country,
  c.region
FROM {s.ref('bronze_complaints')} p
JOIN {s.ref('silver_customers')} c ON c.customer_id = p.customer_id"""

    def aml_sql(s: Sql) -> str:
        return f"""
SELECT
  a.alert_id,
  a.customer_id,
  a.txn_id,
  a.alert_ts,
  CAST(a.alert_ts AS DATE) AS alert_date,
  a.rule_code,
  a.risk_score,
  CASE WHEN a.risk_score >= 75 THEN 'HIGH' WHEN a.risk_score >= 40 THEN 'MEDIUM' ELSE 'LOW' END AS risk_level,
  a.alert_status,
  a.analyst_notes,
  t.amount_aud AS txn_amount_aud,
  c.country,
  c.region
FROM {s.ref('bronze_aml_alerts')} a
JOIN {s.ref('silver_customers')} c ON c.customer_id = a.customer_id
LEFT JOIN {s.ref('silver_transactions')} t ON t.txn_id = a.txn_id"""

    return [
        Derived("silver_branches", "Branches with region.", branches_sql),
        Derived("silver_customers", "Customers with tidied names and emails, current address, age band, clean country code and region.", customers_sql),
        Derived("silver_kyc_documents", "Identity documents with an expiry flag and the customer's region.", kyc_sql),
        Derived("silver_accounts", "Accounts with product name, AUD balance and the customer's region.", accounts_sql),
        Derived("silver_transactions", "Transactions without duplicates, with direction, signed and AUD amounts, branch and region.", transactions_sql),
        Derived("silver_cards", "Cards with the customer and region.", cards_sql),
        Derived("silver_home_loans", "Home loans with loan-to-value ratio, arrears bucket and region.", home_loans_sql),
        Derived("silver_crm_interactions", "CRM interactions with the customer's region.", crm_sql),
        Derived("silver_complaints", "Complaints with days open, month received and region.", complaints_sql),
        Derived("silver_aml_alerts", "AML alerts with risk level, transaction amount and region.", aml_sql),
    ]


def gold() -> list[Derived]:
    def deposits_sql(s: Sql) -> str:
        return f"""
SELECT
  t.txn_date,
  t.branch_id,
  b.branch_name,
  t.region,
  t.country,
  COUNT(*) AS deposit_count,
  SUM(t.amount_aud) AS total_deposits_aud,
  SUM(CASE WHEN t.channel IN ('BRANCH', 'ATM') THEN t.amount_aud ELSE 0 END) AS cash_deposits_aud,
  SUM(CASE WHEN t.channel = 'DIRECT_CREDIT' THEN t.amount_aud ELSE 0 END) AS salary_deposits_aud
FROM {s.ref('silver_transactions')} t
LEFT JOIN {s.ref('silver_branches')} b ON b.branch_id = t.branch_id
WHERE t.txn_type = 'DEPOSIT'
GROUP BY 1, 2, 3, 4, 5"""

    def customer_360_sql(s: Sql) -> str:
        return f"""
WITH accounts AS (
  SELECT customer_id, COUNT(*) AS accounts, SUM(current_balance_aud) AS total_balance_aud
  FROM {s.ref('silver_accounts')}
  WHERE account_status <> 'CLOSED'
  GROUP BY customer_id
),
cards AS (
  SELECT customer_id, COUNT(*) AS cards FROM {s.ref('silver_cards')} WHERE card_status = 'ACTIVE' GROUP BY customer_id
),
loans AS (
  SELECT customer_id, SUM(current_balance) AS home_loan_balance, MAX(days_in_arrears) AS home_loan_days_in_arrears
  FROM {s.ref('silver_home_loans')}
  GROUP BY customer_id
),
complaints AS (
  SELECT customer_id, SUM(CASE WHEN complaint_status <> 'RESOLVED' THEN 1 ELSE 0 END) AS open_complaints
  FROM {s.ref('silver_complaints')}
  GROUP BY customer_id
),
alerts AS (
  SELECT customer_id, SUM(CASE WHEN alert_status IN ('OPEN', 'UNDER_REVIEW') THEN 1 ELSE 0 END) AS open_aml_alerts
  FROM {s.ref('silver_aml_alerts')}
  GROUP BY customer_id
),
last_contact AS (
  SELECT customer_id, interaction_date, topic, notes,
         ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY interaction_ts DESC) AS rn
  FROM {s.ref('silver_crm_interactions')}
)
SELECT
  c.customer_id,
  c.first_name,
  c.last_name,
  c.email,
  c.age_band,
  c.segment,
  c.customer_status,
  c.home_branch_name,
  c.country,
  c.region,
  COALESCE(a.accounts, 0) AS accounts,
  COALESCE(a.total_balance_aud, 0) AS total_balance_aud,
  COALESCE(k.cards, 0) AS active_cards,
  CASE WHEN l.customer_id IS NULL THEN FALSE ELSE TRUE END AS has_home_loan,
  COALESCE(l.home_loan_balance, 0) AS home_loan_balance,
  l.home_loan_days_in_arrears,
  COALESCE(p.open_complaints, 0) AS open_complaints,
  COALESCE(x.open_aml_alerts, 0) AS open_aml_alerts,
  lc.interaction_date AS last_contact_date,
  lc.topic AS last_contact_topic,
  lc.notes AS last_contact_notes
FROM {s.ref('silver_customers')} c
LEFT JOIN accounts a ON a.customer_id = c.customer_id
LEFT JOIN cards k ON k.customer_id = c.customer_id
LEFT JOIN loans l ON l.customer_id = c.customer_id
LEFT JOIN complaints p ON p.customer_id = c.customer_id
LEFT JOIN alerts x ON x.customer_id = c.customer_id
LEFT JOIN last_contact lc ON lc.customer_id = c.customer_id AND lc.rn = 1"""

    def complaint_themes_sql(s: Sql) -> str:
        return f"""
WITH latest AS (
  SELECT received_month, category, region, description,
         ROW_NUMBER() OVER (PARTITION BY received_month, category, region ORDER BY received_date DESC, complaint_id) AS rn
  FROM {s.ref('silver_complaints')}
),
summary AS (
  SELECT
    received_month,
    category,
    region,
    COUNT(*) AS complaints,
    SUM(CASE WHEN complaint_status <> 'RESOLVED' THEN 1 ELSE 0 END) AS unresolved,
    SUM(CASE WHEN complaint_status = 'ESCALATED' THEN 1 ELSE 0 END) AS escalated,
    ROUND(AVG(CASE WHEN complaint_status = 'RESOLVED' THEN days_open END), 1) AS avg_days_to_resolve,
    SUM(compensation_amount) AS total_compensation
  FROM {s.ref('silver_complaints')}
  GROUP BY 1, 2, 3
)
SELECT s.*, l.description AS latest_example
FROM summary s
LEFT JOIN latest l ON l.received_month = s.received_month AND l.category = s.category AND l.region = s.region AND l.rn = 1"""

    def aml_sql(s: Sql) -> str:
        return f"""
SELECT
  alert_date,
  rule_code,
  risk_level,
  alert_status,
  region,
  COUNT(*) AS alerts,
  COUNT(DISTINCT customer_id) AS customers,
  ROUND(AVG(CAST(risk_score AS {s.d.type('decimal(6,2)')})), 1) AS avg_risk_score,
  SUM(txn_amount_aud) AS total_txn_amount_aud
FROM {s.ref('silver_aml_alerts')}
GROUP BY 1, 2, 3, 4, 5"""

    def home_loans_sql(s: Sql) -> str:
        return f"""
SELECT
  region,
  country,
  state,
  rate_type,
  arrears_bucket,
  COUNT(*) AS loans,
  SUM(current_balance) AS total_balance,
  ROUND(AVG(loan_to_value_pct), 1) AS avg_loan_to_value_pct,
  SUM(CASE WHEN loan_to_value_pct > 80 THEN 1 ELSE 0 END) AS loans_over_80_pct_lvr,
  ROUND(AVG(interest_rate), 2) AS avg_interest_rate
FROM {s.ref('silver_home_loans')}
GROUP BY 1, 2, 3, 4, 5"""

    return [
        Derived("gold_daily_deposits", "Deposits per day and branch in AUD, split into cash and salary. Answers 'what were total deposits today'.", deposits_sql),
        Derived("gold_customer_360", "One row per customer: balances, cards, home loan, complaints, AML alerts and their last contact with notes.", customer_360_sql),
        Derived("gold_complaint_themes", "Complaints per month, category and region, with resolution times, compensation and the latest example.", complaint_themes_sql),
        Derived("gold_aml_overview", "AML alerts per day, rule, risk level, status and region, with customers and amounts.", aml_sql),
        Derived("gold_home_loan_portfolio", "Home loan book by region, state, rate type and arrears bucket, with LVR.", home_loans_sql),
    ]


def schema() -> Schema:
    return Schema(
        "retail_banking",
        "Harbourstone Retail Banking",
        "Personal banking: customers, identity checks, deposit accounts, transactions, cards, home loans, "
        "customer contacts, complaints and anti-money laundering alerts. Sources: core banking (CBS), "
        "card management, lending, CRM, the KYC vendor and the AML engine.",
        bronze(), silver(), gold(),
    )
