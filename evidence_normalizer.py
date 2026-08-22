# ============================================================
# TRUSTLENS - EVIDENCE NORMALIZER
# ============================================================


def safe_get(data, key, default=None):
    """
    Safely get a value from a dictionary.
    """

    if not isinstance(data, dict):
        return default

    return data.get(key, default)


# ============================================================
# WHOIS NORMALIZATION
# ============================================================

def normalize_whois(whois_data):
    """
    Convert raw WHOIS data into compact evidence
    for the reasoning layer.
    """

    if not whois_data or not whois_data.get("success"):

        return {
            "available": False,
            "error": safe_get(
                whois_data,
                "error"
            )
        }

    return {

        "available": True,

        "domain": safe_get(
            whois_data,
            "domain"
        ),

        "creation_date": str(
            safe_get(
                whois_data,
                "creation_date"
            )
        ),

        "expiration_date": str(
            safe_get(
                whois_data,
                "expiration_date"
            )
        ),

        "domain_age_years": safe_get(
            whois_data,
            "domain_age_years"
        ),

        "domain_age_days": safe_get(
            whois_data,
            "domain_age_days"
        ),

        "registrar": safe_get(
            whois_data,
            "registrar"
        ),

        "organization": safe_get(
            whois_data,
            "organization"
        ),

        "country": safe_get(
            whois_data,
            "country"
        ),

        "name_servers": safe_get(
            whois_data,
            "name_servers"
        )
    }


# ============================================================
# WEBSITE NORMALIZATION
# ============================================================

def normalize_website(website_data):
    """
    Extract useful website evidence while keeping
    the data compact enough for the LLM.
    """

    if (
        not website_data
        or not website_data.get("success")
    ):

        return {
            "available": False,
            "error": safe_get(
                website_data,
                "error"
            )
        }

    important_pages = safe_get(
        website_data,
        "important_pages",
        {}
    )

    if not isinstance(
        important_pages,
        dict
    ):
        important_pages = {}

    homepage_text = safe_get(
        website_data,
        "homepage_text_preview",
        ""
    ) or ""

    about_text = safe_get(
        website_data,
        "about_text_preview",
        ""
    ) or ""

    team_text = safe_get(
        website_data,
        "team_text_preview",
        ""
    ) or ""

    return {

        "available": True,

        "website": safe_get(
            website_data,
            "website"
        ),

        "title": safe_get(
            website_data,
            "title"
        ),

        "about_page_found": safe_get(
            website_data,
            "about_page_found",
            False
        ),

        "team_page_found": safe_get(
            website_data,
            "team_page_found",
            False
        ),

        "contact_page_found": (
            important_pages.get(
                "contact"
            )
            is not None
        ),

        "important_pages": {

            "about": important_pages.get(
                "about"
            ),

            "team": important_pages.get(
                "team"
            ),

            "contact": important_pages.get(
                "contact"
            )
        },

        "social_links_found": safe_get(
            website_data,
            "social_links_found",
            0
        ),

        "social_links": safe_get(
            website_data,
            "social_links",
            []
        )[:10],

        "possible_address": safe_get(
            website_data,
            "possible_address"
        ),

        # Keep text compact for the LLM

        "homepage_text": homepage_text[:1500],

        "about_text": about_text[:1200],

        "team_text": team_text[:1200]
    }


# ============================================================
# GITHUB NORMALIZATION
# ============================================================

def normalize_github(github_data):
    """
    Normalize GitHub evidence produced by
    collect_github_evidence().
    """

    if (
        not github_data
        or not github_data.get("success")
    ):

        return {

            "available": False,

            "error": safe_get(
                github_data,
                "error"
            ),

            "limitations": safe_get(
                github_data,
                "limitations",
                []
            )
        }

    organization = safe_get(
        github_data,
        "organization",
        {}
    )

    organization_match = safe_get(
        github_data,
        "organization_match",
        {}
    )

    repository_analysis = safe_get(
        github_data,
        "repository_analysis",
        {}
    )

    derived_signals = safe_get(
        github_data,
        "derived_signals",
        []
    )

    top_repositories = safe_get(
        repository_analysis,
        "top_repositories",
        []
    )

    compact_repositories = []

    for repo in top_repositories[:10]:

        compact_repositories.append({

            "name":
                repo.get("name"),

            "description":
                repo.get("description"),

            "language":
                repo.get("language"),

            "stars":
                repo.get("stars"),

            "forks":
                repo.get("forks"),

            "updated_at":
                repo.get("updated_at"),

            "days_since_update":
                repo.get(
                    "days_since_update"
                )
        })

    return {

        "available": True,

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
                    "github_url"
                ),

            "website":
                organization.get(
                    "website"
                ),

            "company":
                organization.get(
                    "company"
                ),

            "location":
                organization.get(
                    "location"
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
                organization_match.get(
                    "confidence"
                ),

            "score":
                organization_match.get(
                    "score"
                ),

            "reasons":
                organization_match.get(
                    "reasons",
                    []
                )
        },

        "repository_activity": {

            "public_repo_count":
                repository_analysis.get(
                    "public_repo_count"
                ),

            "updated_last_30_days":
                repository_analysis.get(
                    "repositories_updated_last_30_days"
                ),

            "updated_last_90_days":
                repository_analysis.get(
                    "repositories_updated_last_90_days"
                ),

            "updated_last_365_days":
                repository_analysis.get(
                    "repositories_updated_last_365_days"
                )
        },

        "languages":
            repository_analysis.get(
                "languages",
                {}
            ),

        "total_stars":
            repository_analysis.get(
                "total_stars"
            ),

        "total_forks":
            repository_analysis.get(
                "total_forks"
            ),

        "top_repositories":
            compact_repositories,

        "derived_signals":
            derived_signals,

        "limitations":
            github_data.get(
                "limitations",
                []
            )
    }

    # --------------------------------------------------------
    # TOP REPOSITORIES
    # --------------------------------------------------------

    raw_top_repositories = (
        repository_analysis.get(
            "top_repositories",
            []
        )
    )

    top_repositories = []

    for repo in raw_top_repositories[:10]:

        if not isinstance(repo, dict):
            continue

        top_repositories.append({

            "name": repo.get(
                "name"
            ),

            "description": repo.get(
                "description"
            ),

            "language": repo.get(
                "language"
            ),

            "stars": repo.get(
                "stars"
            ),

            "forks": repo.get(
                "forks"
            ),

            "updated_at": repo.get(
                "updated_at"
            ),

            "days_since_update": repo.get(
                "days_since_update"
            ),

            "github_url": repo.get(
                "html_url"
            )
        })

    # --------------------------------------------------------
    # RECENT REPOSITORIES
    # --------------------------------------------------------

    raw_recent_repositories = (
        repository_analysis.get(
            "recent_repositories",
            []
        )
    )

    recent_repositories = []

    for repo in raw_recent_repositories[:10]:

        if not isinstance(repo, dict):
            continue

        recent_repositories.append({

            "name": repo.get(
                "name"
            ),

            "language": repo.get(
                "language"
            ),

            "stars": repo.get(
                "stars"
            ),

            "updated_at": repo.get(
                "updated_at"
            ),

            "days_since_update": repo.get(
                "days_since_update"
            ),

            "github_url": repo.get(
                "html_url"
            )
        })

    # --------------------------------------------------------
    # ORGANIZATION CANDIDATES
    # --------------------------------------------------------

    raw_candidates = (
        organization_match.get(
            "candidate_comparison",
            []
        )
    )

    candidates = []

    for candidate in raw_candidates[:5]:

        if not isinstance(candidate, dict):
            continue

        candidates.append({

            "login": candidate.get(
                "login"
            ),

            "name": candidate.get(
                "name"
            ),

            "score": candidate.get(
                "score"
            )
        })

    return {

        "available": True,

        # ----------------------------------------------------
        # ORGANIZATION
        # ----------------------------------------------------

        "organization": {

            "login": organization.get(
                "login"
            ),

            "name": organization.get(
                "name"
            ),

            "description": organization.get(
                "description"
            ),

            "github_url": organization.get(
                "github_url"
            ),

            "website": organization.get(
                "website"
            ),

            "company": organization.get(
                "company"
            ),

            "location": organization.get(
                "location"
            ),

            "followers": organization.get(
                "followers"
            ),

            "created_at": organization.get(
                "created_at"
            )
        },

        # ----------------------------------------------------
        # ORGANIZATION MATCH
        # ----------------------------------------------------

        "organization_match": {

            "confidence": organization_match.get(
                "confidence"
            ),

            "score": organization_match.get(
                "score"
            ),

            "reasons": organization_match.get(
                "reasons",
                []
            ),

            "candidate_comparison": candidates
        },

        # ----------------------------------------------------
        # REPOSITORY ACTIVITY
        # ----------------------------------------------------

        "repository_activity": {

            "public_repo_count": repository_analysis.get(
                "public_repo_count"
            ),

            "repositories_updated_last_30_days":
                repository_analysis.get(
                    "repositories_updated_last_30_days"
                ),

            "repositories_updated_last_90_days":
                repository_analysis.get(
                    "repositories_updated_last_90_days"
                ),

            "repositories_updated_last_365_days":
                repository_analysis.get(
                    "repositories_updated_last_365_days"
                ),

            "total_stars": repository_analysis.get(
                "total_stars"
            ),

            "total_forks": repository_analysis.get(
                "total_forks"
            )
        },

        # ----------------------------------------------------
        # LANGUAGES
        # ----------------------------------------------------

        "languages": repository_analysis.get(
            "languages",
            {}
        ),

        # ----------------------------------------------------
        # REPOSITORIES
        # ----------------------------------------------------

        "top_repositories": top_repositories,

        "recent_repositories": recent_repositories,

        # ----------------------------------------------------
        # DERIVED SIGNALS
        # ----------------------------------------------------

        "derived_signals": derived_signals,

        # ----------------------------------------------------
        # LIMITATIONS
        # ----------------------------------------------------

        "limitations": safe_get(
            github_data,
            "limitations",
            []
        )
    }


# ============================================================
# TAVILY NORMALIZATION
# ============================================================

def normalize_tavily(tavily_data):
    """
    Extract compact external evidence.

    Search snippets are treated as evidence
    pointers, not automatically verified facts.
    """

    if (
        not tavily_data
        or not tavily_data.get("success")
    ):

        return {

            "available": False,

            "error": safe_get(
                tavily_data,
                "error"
            ),

            "limitations": safe_get(
                tavily_data,
                "limitations",
                []
            )
        }

    evidence = safe_get(
        tavily_data,
        "evidence",
        {}
    )

    if not isinstance(
        evidence,
        dict
    ):
        evidence = {}

    normalized_evidence = {}

    for category, category_data in evidence.items():

        if not isinstance(
            category_data,
            dict
        ):
            continue

        results = category_data.get(
            "results",
            []
        )

        compact_results = []

        for result in results[:5]:

            if not isinstance(
                result,
                dict
            ):
                continue

            compact_results.append({

                "title": result.get(
                    "title"
                ),

                "url": result.get(
                    "url"
                ),

                "content": (
                    result.get(
                        "content"
                    )
                    or ""
                )[:700],

                "source_type": result.get(
                    "source_type"
                ),

                "evidence_confidence": result.get(
                    "evidence_confidence"
                ),

                "search_score": result.get(
                    "search_score"
                )
            })

        normalized_evidence[category] = {

            "result_count": len(
                compact_results
            ),

            "results": compact_results
        }

    return {

        "available": True,

        "company_name": safe_get(
            tavily_data,
            "company_name"
        ),

        "company_domain": safe_get(
            tavily_data,
            "company_domain"
        ),

        "evidence_statistics": safe_get(
            tavily_data,
            "evidence_statistics",
            {}
        ),

        "categories": normalized_evidence,

        "limitations": safe_get(
            tavily_data,
            "limitations",
            []
        )
    }


# ============================================================
# MASTER NORMALIZER
# ============================================================

def build_evidence_packet(
    domain,
    whois_data,
    website_data,
    github_data,
    tavily_data
):
    """
    Combine all collector outputs into one
    consistent evidence packet.

    This packet is passed to the reasoning layer.
    """

    return {

        "company_domain": domain,

        "evidence": {

            "whois": normalize_whois(
                whois_data
            ),

            "website": normalize_website(
                website_data
            ),

            "github": normalize_github(
                github_data
            ),

            "external_search": normalize_tavily(
                tavily_data
            )
        },

        # These rules are passed to the LLM so that
        # collector limitations are not mistaken for
        # negative company signals.

        "reasoning_rules": [

            "Evaluate only the evidence provided.",

            "Do not invent facts that are not present in the evidence.",

            "Missing information is not automatically a negative signal.",

            "A collector failing to find something does not prove that it does not exist.",

            "Website scraping limitations may result from JavaScript rendering, unusual navigation, robots rules, or crawler limitations.",

            "The absence of a GitHub organization does not indicate fraud or lack of engineering activity.",

            "Private GitHub repositories and internal engineering activity are not visible.",

            "The absence of funding information does not indicate illegitimacy.",

            "The absence of negative news does not prove the absence of risk.",

            "Search snippets are evidence pointers and should not automatically be treated as verified facts.",

            "Official company sources may describe claims but independent sources provide stronger external corroboration.",

            "A well-known brand should not receive a negative assessment solely because the website collector did not find an About page, Team page, social link, or physical address.",

            "Distinguish clearly between positive evidence, neutral absence of evidence, information requiring verification, and genuine inconsistencies.",

            "Only call something suspicious when there is concrete evidence of a contradiction, inconsistency, or materially concerning signal.",

            "Repository count, social media presence, funding information, and domain age are supporting signals rather than standalone proof of legitimacy."
        ]
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Evidence normalizer loaded successfully."
    )