import whois
from datetime import datetime, date


def clean_domain(domain):
    domain = (
        domain.strip()
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )

    return domain


def normalize_datetime(value):
    if isinstance(value, datetime):

        if value.tzinfo is not None:
            value = value.replace(tzinfo=None)

    return value


def normalize_date(value, mode="min"):

    if isinstance(value, list):

        values = [
            normalize_datetime(item)
            for item in value
            if item is not None
        ]

        if not values:
            return None

        if mode == "min":
            return min(values)

        return max(values)

    return normalize_datetime(value)


def calculate_domain_age(creation_date):

    if not creation_date:
        return None, None

    if isinstance(creation_date, datetime):
        creation_date = creation_date.date()

    age_days = (
        date.today() - creation_date
    ).days

    age_years = round(
        age_days / 365.25,
        2
    )

    return age_days, age_years


def get_domain_age_signal(age_years):
    """
    Deterministic interpretation.
    This is NOT a legitimacy verdict.
    """

    if age_years is None:

        return {
            "level": "unknown",
            "reason": "Domain creation date was not available."
        }

    if age_years >= 10:

        return {
            "level": "strong",
            "reason": (
                "The domain has existed for more than "
                "10 years."
            )
        }

    if age_years >= 3:

        return {
            "level": "moderate_to_strong",
            "reason": (
                "The domain has existed for multiple years."
            )
        }

    if age_years >= 1:

        return {
            "level": "moderate",
            "reason": (
                "The domain has existed for more than one year."
            )
        }

    return {
        "level": "new",
        "reason": (
            "The domain is relatively new. "
            "Domain age alone does not determine legitimacy."
        )
    }


def clean_name_servers(name_servers):

    if not name_servers:
        return []

    if isinstance(name_servers, str):
        name_servers = [name_servers]

    return sorted(
        list(
            set(
                server.lower()
                for server in name_servers
            )
        )
    )


def get_domain_info(domain):

    domain = clean_domain(domain)

    try:

        print(
            f"\n🔍 Looking up WHOIS information for: "
            f"{domain}"
        )

        raw = whois.whois(domain)

        creation_date = normalize_date(
            raw.creation_date,
            "min"
        )

        expiration_date = normalize_date(
            raw.expiration_date,
            "max"
        )

        age_days, age_years = (
            calculate_domain_age(
                creation_date
            )
        )

        registrar = getattr(
            raw,
            "registrar",
            None
        )

        organization = getattr(
            raw,
            "org",
            None
        )

        country = getattr(
            raw,
            "country",
            None
        )

        name_servers = clean_name_servers(
            getattr(
                raw,
                "name_servers",
                None
            )
        )

        age_signal = get_domain_age_signal(
            age_years
        )

        return {

            "success": True,

            "domain": domain,

            "registration": {

                "creation_date": (
                    creation_date.isoformat()
                    if creation_date
                    else None
                ),

                "expiration_date": (
                    expiration_date.isoformat()
                    if expiration_date
                    else None
                ),

                "age_years": age_years,

                "age_days": age_days
            },

            "registrar": registrar,

            "registrant": {

                "organization": organization,

                "country": country,

                "publicly_identifiable": bool(
                    organization or country
                )
            },

            "dns": {

                "name_servers": name_servers,

                "count": len(name_servers)
            },

            "derived_signals": {

                "domain_age": age_signal
            },

            "limitations": [

                "WHOIS information may be limited by "
                "privacy protection.",

                "Missing WHOIS fields do not imply "
                "a negative trust signal.",

                "Domain age alone cannot determine "
                "whether a company is legitimate."
            ]
        }

    except Exception as error:

        return {

            "success": False,

            "domain": domain,

            "error": str(error),

            "limitations": [

                "WHOIS lookup failure does not imply "
                "anything about company legitimacy."
            ]
        }


if __name__ == "__main__":

    domain = input(
        "Enter company domain: "
    )

    result = get_domain_info(domain)

    print("\n" + "=" * 60)
    print("WHOIS RESULT")
    print("=" * 60)

    print(result)