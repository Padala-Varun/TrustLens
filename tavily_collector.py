import os
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