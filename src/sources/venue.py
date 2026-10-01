from __future__ import annotations

import unicodedata

# Upstream names for River's own ground are not stable: the club feed has used
# "Estadio Más Monumental" (the sponsored name) and plain "Estadio Monumental";
# ESPN uses the former. Pinning the exact string silently emptied the calendar
# in September 2026, so match the bare keyword and disambiguate on city.
_VENUE_KEYWORD = "monumental"
_VENUE_CITY = "buenos aires"
# Other grounds called "Monumental" that River genuinely visits: Atlético
# Tucumán's Estadio Monumental José Fierro, and — in Libertadores years —
# Universitario's in Lima and Colo-Colo's in Santiago. The city check excludes
# all three; the name check below is a second line of defence.
_NOT_MONUMENTAL = ("fierro",)


def fold(value: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    folded = (
        unicodedata.normalize("NFKD", value or "")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )
    return " ".join(folded.split())


def is_monumental(venue: str, city: str, country: str) -> bool:
    folded = fold(venue)
    if _VENUE_KEYWORD not in folded:
        return False
    if any(token in folded for token in _NOT_MONUMENTAL):
        return False
    folded_city = fold(city)
    if folded_city:
        return _VENUE_CITY in folded_city
    # City missing from the record: fall back to country so a partial entry
    # still resolves rather than dropping a real home match.
    return fold(country) in ("", "argentina")
