import os
import json
import requests

from datetime import datetime, timezone
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT SETUP
# ============================================================

load_dotenv()

GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "TrustLens"
}


if GITHUB_TOKEN:
    HEADERS["Authorization"] = (
        f"Bearer {GITHUB_TOKEN}"
    )


# ============================================================
# DOMAIN HELPERS
# ============================================================

def clean_domain(domain):
    """
    Convert a URL/domain into a clean domain.

    Examples:
    https://www.lyzr.ai/path -> lyzr.ai
    google.com -> google.com
    """

    if not domain:
        return ""

    domain = domain.strip().lower()

    domain = (
        domain
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )

    return domain


def get_company_name_from_domain(domain):
    """
    Extract the first part of a domain.

    lyzr.ai -> lyzr
    google.com -> google
    """

    domain = clean_domain(domain)

    return domain.split(".")[0]


def domains_match(company_domain, org_website):
    """
    Check whether the GitHub organization's website
    belongs to the company domain.

    Examples:
    google.com <-> cloud.google.com -> True
    lyzr.ai <-> lyzr.ai -> True
    """

    if not company_domain or not org_website:
        return False

    company_domain = clean_domain(
        company_domain
    )

    org_domain = clean_domain(
        org_website
    )

    # Exact match
    if company_domain == org_domain:
        return True

    # GitHub org website is a subdomain
    if org_domain.endswith(
        "." + company_domain
    ):
        return True

    # Company domain is a subdomain
    if company_domain.endswith(
        "." + org_domain
    ):
        return True

    return False


def same_brand(company_domain, org_website):
    """
    Same name on a different TLD.

    stripe.com <-> stripe.dev -> True
    """

    if not company_domain or not org_website:
        return False

    org_labels = clean_domain(
        org_website
    ).split(".")

    if len(org_labels) < 2:
        return False

    return (
        org_labels[-2]
        == get_company_name_from_domain(company_domain)
    )


# ============================================================
# GITHUB API REQUEST HELPER
# ============================================================

def github_get(endpoint, params=None):
    """
    Make a GET request to the GitHub REST API.
    """

    try:

        response = requests.get(
            f"{GITHUB_API}{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=20
        )

        # Rate limit information
        remaining = response.headers.get(
            "X-RateLimit-Remaining"
        )

        if response.status_code == 404:

            return {
                "success": False,
                "status_code": 404,
                "data": None,
                "error": "Not found",
                "rate_limit_remaining": remaining
            }

        if response.status_code == 401:

            return {
                "success": False,
                "status_code": 401,
                "data": None,
                "error": (
                    "GitHub authentication failed. "
                    "Check your GITHUB_TOKEN."
                ),
                "rate_limit_remaining": remaining
            }

        if response.status_code == 403:

            return {
                "success": False,
                "status_code": 403,
                "data": None,
                "error": (
                    "GitHub API rate limit reached "
                    "or permission denied."
                ),
                "rate_limit_remaining": remaining
            }

        response.raise_for_status()

        return {
            "success": True,
            "status_code": response.status_code,
            "data": response.json(),
            "rate_limit_remaining": remaining
        }

    except requests.RequestException as error:

        return {
            "success": False,
            "status_code": None,
            "data": None,
            "error": str(error)
        }


# ============================================================
# SEARCH GITHUB ORGANIZATIONS
# ============================================================

def search_github_organizations(company_name):
    """
    Search GitHub for organizations related to
    the company name.
    """

    query = f"{company_name} type:org"

    result = github_get(
        "/search/users",
        params={
            "q": query,
            "per_page": 10
        }
    )

    if not result["success"]:

        return {
            "success": False,
            "organizations": [],
            "error": result.get("error")
        }

    organizations = result["data"].get(
        "items",
        []
    )

    return {
        "success": True,
        "organizations": organizations
    }


# ============================================================
# GET ORGANIZATION DETAILS
# ============================================================

def get_organization_details(org_login):
    """
    Fetch detailed information about a GitHub organization.
    """

    result = github_get(
        f"/orgs/{org_login}"
    )

    if not result["success"]:
        return None

    data = result["data"]

    return {
        "login": data.get("login"),
        "name": data.get("name"),
        "description": data.get("description"),
        "blog": data.get("blog"),
        "location": data.get("location"),
        "company": data.get("company"),
        "public_repos": data.get("public_repos"),
        "followers": data.get("followers"),
        "html_url": data.get("html_url"),
        "created_at": data.get("created_at")
    }


# ============================================================
# NAME MATCHING
# ============================================================

def calculate_name_match_score(
    company_name,
    org_login,
    org_name,
    description=None,
    company_field=None
):
    """
    Calculate a confidence score using GitHub
    organization metadata.
    """

    score = 0
    reasons = []

    company_name = (
        company_name or ""
    ).lower().strip()

    org_login = (
        org_login or ""
    ).lower().strip()

    org_name = (
        org_name or ""
    ).lower().strip()

    description = (
        description or ""
    ).lower()

    company_field = (
        company_field or ""
    ).lower()

    # ------------------------------------------------
    # Exact login match
    # ------------------------------------------------

    if org_login == company_name:

        score += 60

        reasons.append(
            "GitHub organization login exactly "
            "matches the company name."
        )

    # ------------------------------------------------
    # Company name appears in login
    # Example:
    # company = lyzr
    # org_login = NeuralgoLyzr
    # ------------------------------------------------

    elif (
        len(company_name) >= 3
        and company_name in org_login
    ):

        score += 45

        reasons.append(
            "GitHub organization login contains "
            "the company name."
        )

    # ------------------------------------------------
    # Exact organization name
    # ------------------------------------------------

    if org_name == company_name:

        score += 50

        reasons.append(
            "GitHub organization name exactly "
            "matches the company name."
        )

    # ------------------------------------------------
    # Partial organization name match
    # ------------------------------------------------

    elif (
        len(company_name) >= 3
        and company_name in org_name
    ):

        score += 30

        reasons.append(
            "GitHub organization name contains "
            "the company name."
        )

    # ------------------------------------------------
    # Description match
    # ------------------------------------------------

    if (
        len(company_name) >= 3
        and company_name in description
    ):

        score += 20

        reasons.append(
            "GitHub organization description "
            "mentions the company name."
        )

    # ------------------------------------------------
    # Company field match
    # ------------------------------------------------

    if (
        len(company_name) >= 3
        and company_name in company_field
    ):

        score += 25

        reasons.append(
            "GitHub organization company field "
            "mentions the company name."
        )

    return score, reasons


# ============================================================
# FIND BEST GITHUB ORGANIZATION
# ============================================================

def find_best_organization(company_domain):
    """
    Search possible GitHub organizations and
    select the best candidate.
    """

    company_domain = clean_domain(
        company_domain
    )

    company_name = (
        get_company_name_from_domain(
            company_domain
        )
    )

    search_result = (
        search_github_organizations(
            company_name
        )
    )

    if not search_result["success"]:

        return {
            "found": False,
            "api_error": True,
            "error": search_result.get(
                "error"
            )
        }

    candidates = []

    for org in search_result[
        "organizations"
    ]:

        org_login = org.get("login")

        if not org_login:
            continue

        details = (
            get_organization_details(
                org_login
            )
        )

        if not details:
            continue

        score = 0
        reasons = []

        # --------------------------------------------
        # Strongest evidence:
        # Organization website matches company domain
        # --------------------------------------------

        domain_link = 0

        if domains_match(
            company_domain,
            details.get("blog")
        ):

            domain_link = 2

            score += 100

            reasons.append(
                "GitHub organization website "
                "matches or belongs to the "
                "company domain."
            )

        elif same_brand(
            company_domain,
            details.get("blog")
        ):

            domain_link = 1

            score += 70

            reasons.append(
                "GitHub organization website uses "
                "the company name on a different "
                "domain extension."
            )

        # --------------------------------------------
        # Name-based evidence
        # --------------------------------------------

        name_score, name_reasons = (
            calculate_name_match_score(

                company_name=company_name,

                org_login=org_login,

                org_name=details.get(
                    "name"
                ),

                description=details.get(
                    "description"
                ),

                company_field=details.get(
                    "company"
                )
            )
        )

        score += name_score

        reasons.extend(
            name_reasons
        )

        candidates.append({

            "details": details,

            "score": score,

            "reasons": reasons,

            "domain_link": domain_link,

            "exact_login":
                org_login.lower() == company_name
        })

    if not candidates:

        return {
            "found": False,
            "error": (
                "No GitHub organization "
                "candidates found."
            )
        }

    # Prefer the main org: linked to the company's website
    # AND named exactly like the company (stripe over
    # stripe-samples). Then stronger website links, then score.

    candidates.sort(
        key=lambda item: (
            item["domain_link"] > 0
            and item["exact_login"],
            item["domain_link"],
            item["score"]
        ),
        reverse=True
    )

    best = candidates[0]

    # --------------------------------------------
    # Confidence classification
    # --------------------------------------------

    if best["score"] >= 100:

        confidence = "high"

    elif best["score"] >= 50:

        confidence = "medium"

    elif best["score"] >= 20:

        confidence = "low"

    else:

        return {
            "found": False,
            "error": (
                "GitHub organization candidates "
                "were found, but none could be "
                "confidently matched."
            )
        }

    return {

        "found": True,

        "organization":
            best["details"],

        "match_confidence":
            confidence,

        "match_score":
            best["score"],

        "match_reasons":
            best["reasons"],

        "all_candidates": [

            {
                "login":
                    candidate[
                        "details"
                    ].get("login"),

                "name":
                    candidate[
                        "details"
                    ].get("name"),

                "score":
                    candidate["score"]
            }

            for candidate in candidates[:5]
        ]
    }


# ============================================================
# GET ALL ORGANIZATION REPOSITORIES
# ============================================================

MAX_REPOSITORY_PAGES = 3


def get_organization_repositories(org_login):
    """
    Fetch public repositories using pagination.

    Capped at MAX_REPOSITORY_PAGES (most recently updated
    first) so very large organizations do not exhaust
    the API rate limit.
    """

    all_repositories = []

    page = 1
    per_page = 100

    while page <= MAX_REPOSITORY_PAGES:

        result = github_get(

            f"/orgs/{org_login}/repos",

            params={

                "type": "public",

                "sort": "updated",

                "direction": "desc",

                "per_page": per_page,

                "page": page
            }
        )

        if not result["success"]:

            break

        repositories = result["data"]

        if not repositories:
            break

        all_repositories.extend(
            repositories
        )

        print(
            f"   Fetched "
            f"{len(all_repositories)} "
            f"repositories..."
        )

        # Last page

        if len(repositories) < per_page:
            break

        page += 1

    return all_repositories


# ============================================================
# DATE HELPERS
# ============================================================

def days_since(date_string):
    """
    Calculate how many days have passed since
    a GitHub timestamp.
    """

    if not date_string:
        return None

    try:

        date_value = (
            datetime.fromisoformat(
                date_string.replace(
                    "Z",
                    "+00:00"
                )
            )
        )

        now = datetime.now(
            timezone.utc
        )

        return (
            now - date_value
        ).days

    except Exception:

        return None


# ============================================================
# REPOSITORY ANALYSIS
# ============================================================

def analyze_repositories(repositories):
    """
    Analyze repository activity, languages,
    stars and forks.
    """

    languages = {}

    total_stars = 0
    total_forks = 0

    recent_30_days = []
    recent_90_days = []
    recent_365_days = []

    top_repositories = []

    for repo in repositories:

        language = repo.get(
            "language"
        )

        # Language statistics

        if language:

            languages[language] = (
                languages.get(
                    language,
                    0
                )
                + 1
            )

        # Stars

        stars = repo.get(
            "stargazers_count",
            0
        )

        # Forks

        forks = repo.get(
            "forks_count",
            0
        )

        total_stars += stars
        total_forks += forks

        updated_at = repo.get(
            "updated_at"
        )

        days_old = days_since(
            updated_at
        )

        repo_info = {

            "name":
                repo.get("name"),

            "description":
                repo.get("description"),

            "language":
                language,

            "stars":
                stars,

            "forks":
                forks,

            "updated_at":
                updated_at,

            "days_since_update":
                days_old,

            "html_url":
                repo.get("html_url")
        }

        # ----------------------------------------
        # Activity buckets
        # ----------------------------------------

        if days_old is not None:

            if days_old <= 30:

                recent_30_days.append(
                    repo_info
                )

            if days_old <= 90:

                recent_90_days.append(
                    repo_info
                )

            if days_old <= 365:

                recent_365_days.append(
                    repo_info
                )

        top_repositories.append(
            repo_info
        )

    # ----------------------------------------
    # Sort repositories by stars
    # ----------------------------------------

    top_repositories.sort(

        key=lambda repo:
            repo["stars"],

        reverse=True
    )

    # ----------------------------------------
    # Sort languages
    # ----------------------------------------

    top_languages = sorted(

        languages.items(),

        key=lambda item:
            item[1],

        reverse=True
    )

    return {

        "public_repo_count":
            len(repositories),

        "repositories_updated_last_30_days":
            len(recent_30_days),

        "repositories_updated_last_90_days":
            len(recent_90_days),

        "repositories_updated_last_365_days":
            len(recent_365_days),

        "recent_repositories":

            recent_90_days[:10],

        "languages":

            dict(
                top_languages[:10]
            ),

        "total_stars":
            total_stars,

        "total_forks":
            total_forks,

        "top_repositories":

            top_repositories[:10]
    }


# ============================================================
# CREATE TRUST SIGNALS
# ============================================================

def create_github_signals(
    match_confidence,
    repo_analysis
):
    """
    Create conservative evidence signals.

    Important:
    Missing GitHub data is NOT automatically
    treated as suspicious.
    """

    signals = []

    repo_count = (
        repo_analysis[
            "public_repo_count"
        ]
    )

    recent_30 = (
        repo_analysis[
            "repositories_updated_last_30_days"
        ]
    )

    recent_90 = (
        repo_analysis[
            "repositories_updated_last_90_days"
        ]
    )

    # ----------------------------------------
    # Organization verification
    # ----------------------------------------

    if match_confidence == "high":

        signals.append({

            "signal":
                "verified_github_organization",

            "level":
                "positive",

            "reason":
                (
                    "The GitHub organization has "
                    "strong evidence connecting it "
                    "to the company."
                )
        })

    elif match_confidence == "medium":

        signals.append({

            "signal":
                "probable_github_organization",

            "level":
                "positive",

            "reason":
                (
                    "The GitHub organization has "
                    "strong name-based evidence "
                    "linking it to the company."
                )
        })

    else:

        signals.append({

            "signal":
                "possible_github_organization",

            "level":
                "neutral",

            "reason":
                (
                    "A possible GitHub organization "
                    "was identified, but verification "
                    "is limited."
                )
        })

    # ----------------------------------------
    # Public repository presence
    # ----------------------------------------

    if repo_count >= 20:

        signals.append({

            "signal":
                "substantial_public_engineering_presence",

            "level":
                "positive",

            "reason":
                (
                    f"{repo_count} public repositories "
                    f"were observed."
                )
        })

    elif repo_count > 0:

        signals.append({

            "signal":
                "public_engineering_presence",

            "level":
                "neutral",

            "reason":
                (
                    f"{repo_count} public repositories "
                    f"were observed."
                )
        })

    else:

        signals.append({

            "signal":
                "no_public_repositories_observed",

            "level":
                "neutral",

            "reason":
                (
                    "No public repositories were "
                    "observed. Private engineering "
                    "activity cannot be evaluated."
                )
        })

    # ----------------------------------------
    # Recent activity
    # ----------------------------------------

    if recent_30 >= 3:

        signals.append({

            "signal":
                "strong_recent_github_activity",

            "level":
                "positive",

            "reason":
                (
                    f"{recent_30} public repositories "
                    f"were updated within 30 days."
                )
        })

    elif recent_90 >= 3:

        signals.append({

            "signal":
                "recent_github_activity",

            "level":
                "positive",

            "reason":
                (
                    f"{recent_90} public repositories "
                    f"were updated within 90 days."
                )
        })

    elif recent_90 > 0:

        signals.append({

            "signal":
                "limited_recent_github_activity",

            "level":
                "neutral",

            "reason":
                (
                    f"{recent_90} public repositories "
                    f"were updated within 90 days."
                )
        })

    else:

        signals.append({

            "signal":
                "no_recent_public_activity_observed",

            "level":
                "neutral",

            "reason":
                (
                    "No recent public repository "
                    "activity was observed. This does "
                    "not indicate that the company "
                    "is inactive."
                )
        })

    return signals


# ============================================================
# MAIN GITHUB EVIDENCE COLLECTOR
# ============================================================

def collect_github_evidence(company_domain):
    """
    Main function used by TrustLens.
    """

    company_domain = clean_domain(
        company_domain
    )

    print(
        f"\n🐙 Searching GitHub evidence for: "
        f"{company_domain}"
    )

    # ----------------------------------------
    # Find organization
    # ----------------------------------------

    organization_result = (
        find_best_organization(
            company_domain
        )
    )

    if not organization_result[
        "found"
    ]:

        return {

            "success": False,

            "company_domain":
                company_domain,

            "error":
                organization_result.get(
                    "error"
                ),

            # False means "no matching organization",
            # which is neutral evidence, not a failure
            "api_error":
                organization_result.get(
                    "api_error",
                    False
                ),

            "limitations": [

                "A GitHub organization may exist "
                "under a different name.",

                "Private repositories are not visible.",

                "The absence of a GitHub match does "
                "not indicate that the company lacks "
                "engineering activity."
            ]
        }

    organization = (
        organization_result[
            "organization"
        ]
    )

    org_login = organization["login"]

    print(
        f"✓ GitHub organization found: "
        f"{org_login}"
    )

    print(
        f"✓ Match confidence: "
        f"{organization_result['match_confidence']}"
    )

    # ----------------------------------------
    # Fetch repositories
    # ----------------------------------------

    print(
        "\n📦 Fetching public repositories..."
    )

    repositories = (
        get_organization_repositories(
            org_login
        )
    )

    # ----------------------------------------
    # Analyze repositories
    # ----------------------------------------

    print(
        "✓ Analyzing repository activity..."
    )

    repo_analysis = (
        analyze_repositories(
            repositories
        )
    )

    # Fetching is capped, so prefer the count GitHub reports

    reported_repo_count = (
        organization.get("public_repos")
        or 0
    )

    if reported_repo_count > repo_analysis[
        "public_repo_count"
    ]:

        repo_analysis[
            "public_repo_count"
        ] = reported_repo_count

    # ----------------------------------------
    # Create evidence signals
    # ----------------------------------------

    signals = (
        create_github_signals(

            organization_result[
                "match_confidence"
            ],

            repo_analysis
        )
    )

    return {

        "success": True,

        "company_domain":
            company_domain,

        "organization": {

            "login":
                organization.get("login"),

            "name":
                organization.get("name"),

            "description":
                organization.get(
                    "description"
                ),

            "github_url":
                organization.get(
                    "html_url"
                ),

            "website":
                organization.get(
                    "blog"
                ),

            "company":
                organization.get(
                    "company"
                ),

            "location":
                organization.get(
                    "location"
                ),

            "public_repos_reported":
                organization.get(
                    "public_repos"
                ),

            "followers":
                organization.get(
                    "followers"
                ),

            "created_at":
                organization.get(
                    "created_at"
                )
        },

        "organization_match": {

            "confidence":

                organization_result[
                    "match_confidence"
                ],

            "score":

                organization_result[
                    "match_score"
                ],

            "reasons":

                organization_result[
                    "match_reasons"
                ],

            "candidate_comparison":

                organization_result[
                    "all_candidates"
                ]
        },

        "repository_analysis":

            repo_analysis,

        "derived_signals":

            signals,

        "limitations": [

            "Only public GitHub data is analyzed.",

            "Private repositories and internal "
            "engineering activity are not visible.",

            "Repository count alone does not "
            "indicate company legitimacy.",

            "GitHub activity should be treated "
            "as supporting evidence rather than "
            "proof of legitimacy."
        ]
    }


# ============================================================
# RUN DIRECTLY FOR TESTING
# ============================================================

if __name__ == "__main__":

    domain = input(
        "\nEnter company domain: "
    )

    result = collect_github_evidence(
        domain
    )

    print("\n" + "=" * 60)
    print("GITHUB EVIDENCE RESULT")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=2
        )
    )