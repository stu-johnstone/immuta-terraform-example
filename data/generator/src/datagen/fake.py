"""Deterministic fake data. Everything is invented; where a reserved or test
range exists it is used:

- emails: example.com, example.net, example.org (RFC 2606)
- IP addresses: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24 (RFC 5737)
- phones: AU 02/03 5550 xxxx landlines, UK 07700 900xxx and US 555-01xx
  are ranges set aside for fiction; AU mobiles use the 0491 570 block
- cards: Luhn-valid numbers on the 411111 and 555555 test prefixes

Tax file numbers and ABNs pass their checksums, so discovery recognises
them; they are random and must only be used as demo data.

Each table gets its own random generator seeded from its name, so changing
one table does not change the data in any other.
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta
from decimal import Decimal

# Birth dates are fixed relative to this date so they never change.
REFERENCE_DATE = date(2026, 1, 1)

FIRST_NAMES = (
    "Olivia", "Jack", "Charlotte", "William", "Amelia", "Noah", "Isla", "Oliver", "Mia", "Leo",
    "Ava", "Henry", "Grace", "Lucas", "Chloe", "Thomas", "Ruby", "James", "Zoe", "Ethan",
    "Priya", "Arjun", "Wei", "Mei", "Hiroshi", "Yuki", "Minh", "Linh", "Aroha", "Tane",
    "Fatima", "Omar", "Sofia", "Mateo", "Hannah", "Liam", "Emily", "Daniel", "Sarah", "Ahmed",
    "Ananya", "Raj", "Jun", "Siobhan", "Connor", "Maria", "Nikos", "Eleni", "Tom", "Lucy",
    "Kai", "Mila", "Archie", "Harper", "Sienna", "Felix", "Matilda", "Hamish", "Ines", "Ravi",
)
LAST_NAMES = (
    "Smith", "Nguyen", "Williams", "Brown", "Wilson", "Taylor", "Johnson", "White", "Martin",
    "Anderson", "Thompson", "Tran", "Lee", "Walker", "Harris", "Ryan", "Robinson", "Kelly",
    "King", "Chen", "Wang", "Singh", "Patel", "Kumar", "Sharma", "Li", "Zhang", "Tanaka", "Sato",
    "Kim", "Park", "Ngata", "Walsh", "Murphy", "Rossi", "Papadopoulos", "Ali", "Khan", "Hassan",
    "Fernando", "Silva", "Jones", "Davies", "Evans", "Campbell", "Stewart", "Mitchell",
    "Hughes", "Clarke", "Cooper", "Doyle", "Barnes", "Fraser", "Gill", "Okafor", "Mendes",
)

# (city, suburb, state, postcode) by country.
PLACES = {
    "AU": [
        ("Sydney", "Sydney", "NSW", "2000"), ("Sydney", "Parramatta", "NSW", "2150"),
        ("Sydney", "Chatswood", "NSW", "2067"), ("Sydney", "Bondi", "NSW", "2026"),
        ("Newcastle", "Newcastle", "NSW", "2300"), ("Wollongong", "Wollongong", "NSW", "2500"),
        ("Melbourne", "Melbourne", "VIC", "3000"), ("Melbourne", "Richmond", "VIC", "3121"),
        ("Melbourne", "Carlton", "VIC", "3053"), ("Geelong", "Geelong", "VIC", "3220"),
        ("Ballarat", "Ballarat", "VIC", "3350"), ("Brisbane", "Brisbane", "QLD", "4000"),
        ("Brisbane", "Fortitude Valley", "QLD", "4006"), ("Gold Coast", "Southport", "QLD", "4215"),
        ("Townsville", "Townsville", "QLD", "4810"), ("Cairns", "Cairns", "QLD", "4870"),
        ("Perth", "Perth", "WA", "6000"), ("Perth", "Fremantle", "WA", "6160"),
        ("Perth", "Joondalup", "WA", "6027"), ("Adelaide", "Adelaide", "SA", "5000"),
        ("Adelaide", "Glenelg", "SA", "5045"), ("Hobart", "Hobart", "TAS", "7000"),
        ("Launceston", "Launceston", "TAS", "7250"), ("Canberra", "Braddon", "ACT", "2612"),
        ("Darwin", "Darwin", "NT", "0800"),
    ],
    "NZ": [
        ("Auckland", "Ponsonby", "AUK", "1011"), ("Auckland", "Takapuna", "AUK", "0622"),
        ("Wellington", "Te Aro", "WGN", "6011"), ("Christchurch", "Riccarton", "CAN", "8011"),
    ],
    "SG": [
        ("Singapore", "Tanjong Pagar", "SG", "088539"), ("Singapore", "Bukit Timah", "SG", "259760"),
        ("Singapore", "Tampines", "SG", "529510"),
    ],
    "GB": [
        ("London", "Canary Wharf", "LND", "E14 5AB"), ("London", "Islington", "LND", "N1 9GU"),
        ("London", "Southwark", "LND", "SE1 9SG"), ("Manchester", "Manchester", "MAN", "M1 1AE"),
    ],
    "US": [
        ("New York", "Brooklyn", "NY", "11201"), ("Austin", "Austin", "TX", "78701"),
        ("Seattle", "Seattle", "WA", "98101"), ("San Francisco", "San Francisco", "CA", "94105"),
    ],
}
STREETS = (
    "King", "Queen", "George", "Elizabeth", "Church", "High", "Victoria", "Albert", "William",
    "Station", "Park", "Railway", "Beach", "Hill", "Ocean", "Bridge", "Market", "Wattle",
    "Banksia", "Harbour", "Kent", "Clarence", "Macquarie", "Flinders",
)
STREET_TYPES = ("Street", "Road", "Avenue", "Lane", "Parade", "Terrace", "Crescent")
CURRENCIES = {"AU": "AUD", "NZ": "NZD", "SG": "SGD", "GB": "GBP", "US": "USD"}


def rng(*keys: str) -> random.Random:
    """A random generator seeded from the given keys."""
    digest = hashlib.sha256("/".join(keys).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def weighted(r: random.Random, options: dict[str, int]) -> str:
    return r.choices(list(options), weights=list(options.values()))[0]


def chance(r: random.Random, probability: float) -> bool:
    return r.random() < probability


def money(r: random.Random, low: float, high: float) -> Decimal:
    return Decimal(r.randint(int(low * 100), int(high * 100))) / 100


def rate(r: random.Random, low: float, high: float, places: int = 2) -> Decimal:
    scale = 10**places
    return Decimal(r.randint(int(low * scale), int(high * scale))) / scale


def digits(r: random.Random, count: int) -> str:
    return "".join(str(r.randint(0, 9)) for _ in range(count))


def name(r: random.Random) -> tuple[str, str]:
    return r.choice(FIRST_NAMES), r.choice(LAST_NAMES)


def birth_date(r: random.Random, min_age: int, max_age: int) -> date:
    return REFERENCE_DATE - timedelta(days=r.randint(min_age * 365 + 1, max_age * 365))


def email(r: random.Random, first: str, last: str) -> str:
    domain = r.choice(("example.com", "example.net", "example.org"))
    return f"{first}.{last}{r.randint(1, 99)}@{domain}".lower()


def phone(r: random.Random, country: str, mobile: bool = True) -> str:
    if country == "AU":
        if mobile:
            return f"0491 570 {r.randint(100, 999)}"
        return f"0{r.choice('23')} 5550 {digits(r, 4)}"
    if country == "NZ":
        return f"+64 21 555 {digits(r, 4)}"
    if country == "SG":
        return f"+65 8555 {digits(r, 4)}"
    if country == "GB":
        return f"+44 7700 900{digits(r, 3)}"
    return f"+1 202 555 01{digits(r, 2)}"


def address(r: random.Random, country: str) -> dict[str, str]:
    city, suburb, state, postcode = r.choice(PLACES[country])
    street = f"{r.randint(1, 240)} {r.choice(STREETS)} {r.choice(STREET_TYPES)}"
    if chance(r, 0.25):
        street = f"Unit {r.randint(1, 40)}/{street}"
    return {"address_line": street, "suburb": suburb, "city": city, "state": state, "postcode": postcode}


def ip_address(r: random.Random) -> str:
    return f"{r.choice(('192.0.2', '198.51.100', '203.0.113'))}.{r.randint(1, 254)}"


def tfn(r: random.Random) -> str:
    """An Australian tax file number that passes the checksum."""
    weights = (1, 4, 3, 7, 5, 8, 6, 9, 10)
    while True:
        first = [r.randint(0, 9) for _ in range(8)]
        check = (-sum(d * w for d, w in zip(first, weights)) * 10) % 11  # 10 is its own inverse mod 11
        if check < 10:
            value = "".join(map(str, first + [check]))
            return value if chance(r, 0.6) else f"{value[:3]} {value[3:6]} {value[6:]}"


def abn(r: random.Random) -> str:
    """An Australian Business Number that passes the checksum."""
    weights = (10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)
    while True:
        number = [r.randint(1, 9)] + [r.randint(0, 9) for _ in range(10)]
        number_check = [number[0] - 1] + number[1:]
        if sum(d * w for d, w in zip(number_check, weights)) % 89 == 0:
            value = "".join(map(str, number))
            return f"{value[:2]} {value[2:5]} {value[5:8]} {value[8:]}"


def luhn_number(r: random.Random, prefix: str, length: int = 16) -> str:
    body = prefix + digits(r, length - len(prefix) - 1)
    total = 0
    for i, d in enumerate(reversed(body)):
        n = int(d) * (2 if i % 2 == 0 else 1)
        total += n - 9 if n > 9 else n
    return body + str((10 - total % 10) % 10)


def card_number(r: random.Random) -> str:
    return luhn_number(r, r.choice(("411111", "555555")))


def gb_iban(r: random.Random, bank_code: str) -> str:
    bban = bank_code + digits(r, 14)
    rearranged = bban + "GB00"
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return f"GB{98 - int(numeric) % 97:02d}{bban}"


def bsb(r: random.Random, prefix: str) -> str:
    return f"{prefix}-{digits(r, 3)}"


def passport(r: random.Random, country: str) -> str:
    if country == "AU":
        return f"P{r.choice('ABCDEFGHJKLMNRSTU')}{digits(r, 7)}"
    if country == "NZ":
        return f"L{r.choice('ABCDEFGH')}{digits(r, 6)}"
    if country == "SG":
        return f"K{digits(r, 7)}{r.choice('ABCDEFGHJ')}"
    return digits(r, 9)


def drivers_licence(r: random.Random) -> str:
    return digits(r, r.choice((8, 9)))


def vin(r: random.Random) -> str:
    alphabet = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"
    return "".join(r.choice(alphabet) for _ in range(17))


def registration(r: random.Random) -> str:
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    return "".join(r.choice(letters) for _ in range(3)) + digits(r, 2) + r.choice(letters)


def days_back(r: random.Random, low: int, high: int) -> int:
    return r.randint(low, high)


def minute_of_day(r: random.Random, start_hour: int = 7, end_hour: int = 21) -> int:
    return r.randint(start_hour * 60, end_hour * 60 - 1)
