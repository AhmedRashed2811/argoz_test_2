"""Country-aware phone validation shared by lead creation and CSV import.

Mirrors the country digit-length rules used in the Add-Lead frontend
(static/leads/lead_create.js) so a number rejected in the form is also
rejected on the backend (e.g. bulk import). Unknown country codes fall back
to a permissive 6–15 digit check.
"""
from __future__ import annotations

# country_code -> expected national digit count(s) (excluding the country code).
COUNTRY_PHONE_LENGTHS: dict[str, tuple[int, ...]] = {
    "+20": (11,),         # Egypt
    "+971": (9,),         # UAE
    "+966": (9,),         # Saudi Arabia
    "+974": (8,),         # Qatar
    "+965": (8,),         # Kuwait
    "+973": (8,),         # Bahrain
    "+968": (8,),         # Oman
    "+962": (9,),         # Jordan
    "+961": (7, 8),       # Lebanon
    "+963": (9,),         # Syria
    "+44": (10,),         # UK
    "+1": (10,),          # US
    "+33": (9,),          # France
    "+49": (10, 11),      # Germany
    "+90": (10,),         # Turkey
    "+91": (10,),         # India
}


def digits_only(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def validate_phone(country_code: str, phone: str) -> str | None:
    """Return an error message if the number is invalid for its country, else
    None. `phone` may contain separators; only digits are counted."""
    d = digits_only(phone)
    if not d:
        return "Phone is required."
    lengths = COUNTRY_PHONE_LENGTHS.get(country_code)
    if lengths is None:
        if not (6 <= len(d) <= 15):
            return "Phone must be 6-15 digits (no spaces or symbols)."
        return None
    if len(d) not in lengths:
        want = " or ".join(str(n) for n in lengths)
        return f"{country_code} numbers must have {want} digits (got {len(d)})."
    return None
