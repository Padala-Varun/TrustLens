import os
import re
import json
from urllib.parse import urlparse

from dotenv import load_dotenv
from tavily import TavilyClient


# ============================================================
# ENVIRONMENT SETUP
# ============================================================

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise ValueError(
        "TAVILY_API_KEY not found. "
        "Add it to your .env file."
    )


tavily_client = TavilyClient(
    api_key=TAVILY_API_KEY
)


# ============================================================
# DOMAIN HELPERS
# ============================================================

def clean_domain(domain):
    """
    Convert a URL/domain into a clean domain.
    """

    if not domain:
        return ""

    domain = domain.strip().lower()

    return (
        domain
        .replace("https://", "")
        .replace("http://", "")
        .replace("www.", "")
        .split("/")[0]
    )


def get_company_name(domain):
    """
    lyzr.ai -> lyzr
    google.com -> google
    """

    domain = clean_domain(domain)

    return domain.split(".")[0]


# ============================================================
# COMPANY NAME -> DOMAIN RESOLUTION
# ============================================================

DOMAIN_PATTERN = re.compile(
    r"^[a-z0-9-]+(\.[a-z0-9-]+)+$"
)


# Sites that write about companies but are never a
# company's own website
NON_COMPANY_DOMAINS = [

    "wikipedia.org",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "github.com",
    "medium.com",
    "reddit.com",
    "quora.com",
    "crunchbase.com",
    "pitchbook.com",
    "tracxn.com",
    "dealroom.co",
    "zoominfo.com",
    "glassdoor.com",
    "ambitionbox.com",
    "g2.com",
    "trustpilot.com",
    "techcrunch.com",
    "forbes.com",
    "reuters.com",
    "bloomberg.com",
    "businessinsider.com",
    "producthunt.com",
    "ycombinator.com",
    "apps.apple.com",
    "play.google.com"
]


def looks_like_domain(text):
    """
    stripe.com -> True
    Lyzr AI -> False
    """

    return bool(
        DOMAIN_PATTERN.match(
            clean_domain(text)
        )
    )


# Second-level labels used under country TLDs (tcs.co.in)
COUNTRY_SECOND_LEVEL = {
    "co", "com", "org", "net", "ac", "gov", "edu"
}


def registrable_domain(domain):
    """
    docs.lyzr.ai -> lyzr.ai
    www.tcs.co.in -> tcs.co.in
    """

    labels = domain.split(".")

    if (
        len(labels) >= 3
        and labels[-2] in COUNTRY_SECOND_LEVEL
        and len(labels[-1]) == 2
    ):
        return ".".join(labels[-3:])

    return ".".join(labels[-2:])


# TLDs companies commonly use for their main site
GENERIC_TLDS = {
    "ai", "io", "co", "org", "net", "app", "dev", "tech", "so", "xyz"
}


def tld_preference(domain):
    """
    Among equally good matches prefer the global site:
    zoho.com over zoho.com.cn, stripe.com over stripe.dev.
    """

    suffix = domain.split(".", 1)[-1]

    if suffix == "com":
        return 0

    if suffix in GENERIC_TLDS:
        return 1

    return 2


def is_non_company_domain(domain):

    return any(
        domain == blocked
        or domain.endswith("." + blocked)
        for blocked in NON_COMPANY_DOMAINS
    )


# Generic words that make the name search less precise:
# "Lyzr AI" searches better as "Lyzr"
GENERIC_NAME_WORDS = {
    "ai", "inc", "llc", "ltd", "limited", "pvt", "private",
    "corp", "corporation", "co", "company", "technologies",
    "technology", "tech", "labs", "software", "solutions",
    "systems", "group", "global", "the"
}


def strip_generic_words(name):

    kept = [
        word
        for word in name.split()
        if word.lower().strip(".,") not in GENERIC_NAME_WORDS
    ]

    return " ".join(kept)


def find_official_website(name):
    """
    Search for the company's website and return
    (domain, url), or None if no result clearly
    belongs to the company.
    """

    response = tavily_client.search(

        query=f"{name} official website",

        search_depth="basic",

        max_results=10,

        include_answer=False,

        include_raw_content=False
    )

    words = [
        word
        for word in re.split(
            r"[^a-z0-9]+",
            name.lower()
        )
        if word
    ]

    name_tokens = [
        word
        for word in words
        if len(word) >= 3
    ]

    # Labels that count as an exact match:
    # "Lyzr AI" -> lyzr, lyzrai
    # "Tata Consultancy Services" -> tcs
    exact_labels = {
        "".join(name_tokens),
        "".join(words)
    }

    if len(words) >= 2:
        exact_labels.add(
            "".join(word[0] for word in words)
        )

    exact_labels.discard("")

    candidates = []

    for position, item in enumerate(
        response.get("results", [])
    ):

        url = item.get("url") or ""

        domain = (
            urlparse(url)
            .netloc
            .lower()
            .split(":")[0]
        )

        if (
            not domain
            or is_non_company_domain(domain)
        ):
            continue

        # Compare and return the main domain, so
        # docs.lyzr.ai counts as lyzr.ai
        domain = registrable_domain(domain)

        # Only accept results that are clearly about the
        # company: the domain contains part of the name
        # (lyzr.ai), or the page title contains the full
        # name ("TCS: Tata Consultancy Services").

        first_label = domain.split(".")[0]

        exact_match = first_label in exact_labels

        domain_match = any(
            token in first_label
            for token in name_tokens
        )

        title_match = (
            name.lower()
            in (item.get("title") or "").lower()
        )

        # A homepage beats a subpage such as
        # tata.com/business/tcs
        is_homepage = (
            urlparse(url).path.strip("/") == ""
        )

        if exact_match:
            rank = 0
        elif domain_match:
            rank = 1
        elif title_match and is_homepage:
            # A subpage titled with the name is usually a
            # third-party listing (apps.make.com/lyzr-ai)
            rank = 2
        else:
            continue

        candidates.append((
            rank,
            not is_homepage,
            tld_preference(domain),
            position,
            domain,
            url
        ))

    if not candidates:
        return None

    candidates.sort()

    *_, domain, url = candidates[0]

    return domain, url


def resolve_company_domain(query):
    """
    Turn a company name into its official website domain.

    "Lyzr" -> "lyzr.ai"
    "stripe.com" -> "stripe.com" (already a domain)
    """

    query = (query or "").strip()

    if not query:

        return {
            "success": False,
            "error": "No company name or domain provided."
        }

    if looks_like_domain(query):

        return {
            "success": True,
            "domain": clean_domain(query),
            "resolved": False
        }

    print(
        f"\n🔎 Resolving official website for: {query}"
    )

    # Try the name as typed, then without generic words
    # ("Lyzr AI" -> "Lyzr") if the first search is unclear

    search_names = [query]

    short_name = strip_generic_words(query)

    if short_name and short_name.lower() != query.lower():
        search_names.append(short_name)

    for name in search_names:

        try:
            found = find_official_website(name)

        except Exception as error:

            return {
                "success": False,
                "error": f"Website lookup failed: {error}"
            }

        if found:

            domain, url = found

            print(f"✓ Resolved: {query} -> {domain}")

            return {
                "success": True,
                "domain": domain,
                "resolved": True,
                "source_url": url
            }

    return {
        "success": False,
        "error": (
            f"Couldn't find an official website for "
            f"'{query}'. Try entering the domain, "
            f"e.g. stripe.com."
        )
    }


# ============================================================
# SOURCE CLASSIFICATION
# ============================================================

def classify_source(url, company_domain):
    """
    Classify the source into an evidence type.
    """

    parsed = urlparse(url)

    source_domain = (
        parsed.netloc
        .lower()
        .replace("www.", "")
    )

    company_domain = clean_domain(
        company_domain
    )

    # Official company source
    if (
        source_domain == company_domain
        or source_domain.endswith(
            "." + company_domain
        )
    ):
        return "official_company"

    # Official partner / marketplace
    official_partner_domains = [

        "aws.amazon.com",
        "cloud.google.com",
        "microsoft.com",
        "azure.microsoft.com",
        "nvidia.com"
    ]

    if any(
        domain in source_domain
        for domain in official_partner_domains
    ):
        return "official_partner"

    # Reputable news
    news_domains = [

        "techcrunch.com",
        "forbes.com",
        "reuters.com",
        "bloomberg.com",
        "venturebeat.com",
        "inc.com",
        "businessinsider.com",
        "thehindu.com",
        "economictimes.indiatimes.com"
    ]

    if any(
        domain in source_domain
        for domain in news_domains
    ):
        return "reputable_news"

    # Funding databases
    funding_domains = [

        "crunchbase.com",
        "pitchbook.com",
        "tracxn.com",
        "dealroom.co"
    ]

    if any(
        domain in source_domain
        for domain in funding_domains
    ):
        return "funding_database"

    # Review platforms
    review_domains = [

        "glassdoor.com",
        "ambitionbox.com",
        "g2.com",
        "trustpilot.com"
    ]

    if any(
        domain in source_domain
        for domain in review_domains
    ):
        return "review_platform"

    # Social media
    social_domains = [

        "linkedin.com",
        "twitter.com",
        "x.com",
        "facebook.com",
        "instagram.com",
        "youtube.com"
    ]

    if any(
        domain in source_domain
        for domain in social_domains
    ):
        return "social_media"

    return "unknown"


# ============================================================
# SOURCE CONFIDENCE
# ============================================================

def get_source_confidence(
    source_type
):
    """
    Assign a confidence level based on source type.
    """

    high_confidence = [

        "official_company",

        "official_partner",

        "reputable_news"
    ]

    medium_confidence = [

        "funding_database",

        "review_platform"
    ]

    if source_type in high_confidence:
        return "high"

    if source_type in medium_confidence:
        return "medium"

    return "low"


# ============================================================
# RELEVANCE FILTER
# ============================================================

def is_result_relevant(
    result,
    company_name,
    company_domain
):
    """
    Check whether the company appears in
    the title, content, or URL.

    This prevents unrelated search results
    from reaching the LLM.
    """

    title = (
        result.get("title")
        or ""
    ).lower()

    content = (
        result.get("content")
        or ""
    ).lower()

    url = (
        result.get("url")
        or ""
    ).lower()

    company_name = (
        company_name
        .lower()
        .strip()
    )

    company_domain = (
        company_domain
        .lower()
        .strip()
    )

    searchable_text = (
        title
        + " "
        + content
        + " "
        + url
    )

    # Exact company domain is strong evidence
    if company_domain in searchable_text:
        return True

    # Company name must appear
    if company_name in searchable_text:
        return True

    return False


# ============================================================
# TAVILY SEARCH
# ============================================================

def search_tavily(
    query,
    company_name,
    company_domain,
    max_results=8
):
    """
    Run Tavily search and filter irrelevant results.
    """

    try:

        response = tavily_client.search(

            query=query,

            search_depth="advanced",

            max_results=max_results,

            include_answer=False,

            include_raw_content=False
        )

        clean_results = []

        for item in response.get(
            "results",
            []
        ):

            if not is_result_relevant(

                result=item,

                company_name=company_name,

                company_domain=company_domain
            ):
                continue

            url = item.get("url")

            source_type = classify_source(

                url,

                company_domain
            )

            clean_results.append({

                "title":
                    item.get("title"),

                "url":
                    url,

                "content":
                    item.get("content"),

                "search_score":
                    item.get("score"),

                "source_type":
                    source_type,

                "evidence_confidence":
                    get_source_confidence(
                        source_type
                    )
            })

        return {

            "success": True,

            "query": query,

            "results": clean_results,

            "raw_result_count":
                len(
                    response.get(
                        "results",
                        []
                    )
                ),

            "relevant_result_count":
                len(clean_results)
        }

    except Exception as error:

        return {

            "success": False,

            "query": query,

            "results": [],

            "error": str(error)
        }


# ============================================================
# BUILD SEARCH QUERIES
# ============================================================

def build_search_queries(
    company_name,
    company_domain
):
    """
    Build company-specific search queries.
    """

    company_identity = (
        f'"{company_name}" OR '
        f'"{company_domain}"'
    )

    return {

        "funding":

            f'{company_identity} '
            f'funding investors '
            f'funding round',

        "founders":

            f'{company_identity} '
            f'founder CEO co-founder leadership',

        "company_reviews":

            f'{company_identity} '
            f'reviews employees '
            f'Glassdoor AmbitionBox',

        "negative_news":

            f'{company_identity} '
            f'layoffs shutdown lawsuit '
            f'controversy',

        "company_presence":

            f'"{company_domain}" '
            f'company news customers '
            f'partnership'
    }


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_results(evidence):
    """
    Remove duplicate URLs across all categories.
    """

    seen_urls = set()

    for category, category_data in evidence.items():

        unique_results = []

        for result in category_data.get(
            "results",
            []
        ):

            url = result.get("url")

            if not url:
                continue

            normalized_url = (
                url
                .lower()
                .rstrip("/")
            )

            if normalized_url in seen_urls:
                continue

            seen_urls.add(
                normalized_url
            )

            unique_results.append(
                result
            )

        evidence[category][
            "results"
        ] = unique_results

        evidence[category][
            "relevant_result_count"
        ] = len(
            unique_results
        )

    return evidence


# ============================================================
# CREATE EVIDENCE SUMMARY
# ============================================================

def create_evidence_statistics(
    evidence
):
    """
    Create statistics for the reasoning layer.
    """

    total_results = 0

    source_types = {}

    confidence_levels = {}

    for category_data in evidence.values():

        for result in category_data.get(
            "results",
            []
        ):

            total_results += 1

            source_type = (
                result.get(
                    "source_type"
                )
            )

            confidence = (
                result.get(
                    "evidence_confidence"
                )
            )

            source_types[source_type] = (
                source_types.get(
                    source_type,
                    0
                )
                + 1
            )

            confidence_levels[confidence] = (
                confidence_levels.get(
                    confidence,
                    0
                )
                + 1
            )

    return {

        "total_relevant_results":
            total_results,

        "source_types":
            source_types,

        "confidence_levels":
            confidence_levels
    }


# ============================================================
# MAIN COLLECTOR
# ============================================================

def collect_search_evidence(
    company_domain
):
    """
    Main TrustLens external evidence collector.
    """

    company_domain = clean_domain(
        company_domain
    )

    company_name = get_company_name(
        company_domain
    )

    print(
        f"\n🔎 Searching external evidence "
        f"for: {company_name}"
    )

    queries = build_search_queries(

        company_name,

        company_domain
    )

    evidence = {}

    for category, query in queries.items():

        print(
            f"\nSearching: {category}"
        )

        result = search_tavily(

            query=query,

            company_name=company_name,

            company_domain=company_domain,

            max_results=8
        )

        evidence[category] = result

        if result["success"]:

            print(
                f"✓ Raw results: "
                f"{result['raw_result_count']}"
            )

            print(
                f"✓ Relevant results: "
                f"{result['relevant_result_count']}"
            )

        else:

            print(
                "✗ Search failed:"
            )

            print(
                result.get("error")
            )

    # Remove duplicate evidence

    evidence = deduplicate_results(
        evidence
    )

    # Create statistics

    statistics = (
        create_evidence_statistics(
            evidence
        )
    )

    return {

        "success": True,

        "company_domain":
            company_domain,

        "company_name":
            company_name,

        "queries":
            queries,

        "evidence":
            evidence,

        "evidence_statistics":
            statistics,

        "limitations": [

            "Search relevance filtering is based "
            "primarily on company name and domain "
            "matching.",

            "Companies with common names may still "
            "produce ambiguous search results.",

            "Search snippets are not independently "
            "verified facts.",

            "The absence of negative news does not "
            "prove the absence of risk.",

            "Negative or positive claims should be "
            "verified using the linked sources."
        ]
    }


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    domain = input(
        "\nEnter company domain: "
    )

    result = collect_search_evidence(
        domain
    )

    print("\n" + "=" * 60)
    print("TAVILY EXTERNAL EVIDENCE")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )