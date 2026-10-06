import json
import sys

# Collectors print emoji; on Windows a non-UTF-8 stdout raises
# UnicodeEncodeError and makes every collector fail.
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

from whoislook import get_domain_info

from websiteScrap import (
    scrape_company_website
)

from github_collector import (
    collect_github_evidence
)

from tavily_collector import (
    collect_search_evidence,
    resolve_company_domain
)

from evidence_normalizer import (
    build_evidence_packet
)

from mistral_reasoner import (
    analyze_evidence
)


# ============================================================
# ENVIRONMENT SETUP
# ============================================================

load_dotenv()


# ============================================================
# DISPLAY HELPERS
# ============================================================

def print_header():

    print("\n" + "=" * 60)

    print(
        "TRUSTLENS - COMPANY DUE DILIGENCE"
    )

    print("=" * 60)


def print_section(title):

    print("\n" + "-" * 60)

    print(title)

    print("-" * 60)


# ============================================================
# COLLECT WHOIS EVIDENCE
# ============================================================

def run_whois(domain):

    print_section(
        "[1/6] Running WHOIS lookup..."
    )

    try:

        result = get_domain_info(
            domain
        )

        if result.get("success"):

            print(
                "✓ WHOIS lookup completed."
            )

        else:

            print(
                "✗ WHOIS lookup failed."
            )

            print(
                result.get(
                    "error",
                    "Unknown error."
                )
            )

        return result

    except Exception as error:

        print(
            f"✗ WHOIS collector error: {error}"
        )

        return {

            "success": False,

            "error": str(error)
        }


# ============================================================
# COLLECT WEBSITE EVIDENCE
# ============================================================

def run_website(domain):

    print_section(
        "[2/6] Scraping company website..."
    )

    try:

        result = scrape_company_website(
            domain
        )

        if result.get("success"):

            print(
                "✓ Website scraping completed."
            )

        else:

            print(
                "✗ Website scraping failed."
            )

            print(
                result.get(
                    "error",
                    "Unknown error."
                )
            )

        return result

    except Exception as error:

        print(
            f"✗ Website collector error: {error}"
        )

        return {

            "success": False,

            "error": str(error)
        }


# ============================================================
# COLLECT GITHUB EVIDENCE
# ============================================================

def run_github(domain):

    print_section(
        "[3/6] Collecting GitHub evidence..."
    )

    try:

        result = collect_github_evidence(
            domain
        )

        if result.get("success"):

            organization = (
                result
                .get("organization", {})
                .get("login")
            )

            if organization:

                print(
                    "✓ GitHub evidence collected."
                )

                print(
                    f"✓ Organization: {organization}"
                )

            else:

                print(
                    "✓ GitHub evidence collection completed."
                )

        elif result.get("api_error"):

            print(
                "✗ GitHub API error."
            )

            print(
                result.get(
                    "error",
                    "Unknown error."
                )
            )

        else:

            print(
                "⚠ No confidently matched GitHub "
                "organization found."
            )

            print(
                "  This is treated as unavailable "
                "evidence, not a negative signal."
            )

        return result

    except Exception as error:

        print(
            f"✗ GitHub collector error: {error}"
        )

        return {

            "success": False,

            "error": str(error)
        }


# ============================================================
# COLLECT TAVILY EVIDENCE
# ============================================================

def run_tavily(domain):

    print_section(
        "[4/6] Searching external evidence..."
    )

    try:

        result = collect_search_evidence(
            domain
        )

        if result.get("success"):

            statistics = result.get(
                "evidence_statistics",
                {}
            )

            total_results = (
                statistics.get(
                    "total_relevant_results",
                    0
                )
            )

            print(
                "\n✓ External evidence collection "
                "completed."
            )

            print(
                f"✓ Relevant evidence results: "
                f"{total_results}"
            )

        else:

            print(
                "✗ External search failed."
            )

            print(
                result.get(
                    "error",
                    "Unknown error."
                )
            )

        return result

    except Exception as error:

        print(
            f"✗ Tavily collector error: {error}"
        )

        return {

            "success": False,

            "error": str(error)
        }


# ============================================================
# BUILD EVIDENCE PACKET
# ============================================================

def run_evidence_normalization(
    domain,
    whois_result,
    website_result,
    github_result,
    tavily_result
):

    print_section(
        "[5/6] Building normalized evidence packet..."
    )

    try:

        evidence_packet = (
            build_evidence_packet(

                domain=domain,

                whois_data=whois_result,

                website_data=website_result,

                github_data=github_result,

                tavily_data=tavily_result
            )
        )

        print(
            "✓ Evidence packet created."
        )

        return evidence_packet

    except Exception as error:

        print(
            f"✗ Evidence normalization failed: "
            f"{error}"
        )

        return {

            "company_domain": domain,

            "evidence": {},

            "normalization_error": str(
                error
            )
        }


# ============================================================
# RUN MISTRAL REASONING
# ============================================================

def run_mistral_analysis(
    evidence_packet
):

    print_section(
        "[6/6] Generating Mistral evidence analysis..."
    )

    try:

        result = analyze_evidence(
            evidence_packet
        )

        if result.get("success"):

            print(
                "✓ Mistral analysis completed."
            )

        else:

            print(
                "✗ Mistral analysis failed."
            )

            print(
                result.get(
                    "error",
                    "Unknown error."
                )
            )

        return result

    except Exception as error:

        print(
            f"✗ Mistral reasoning error: {error}"
        )

        return {

            "success": False,

            "error": str(error)
        }


# ============================================================
# DISPLAY FINAL ANALYSIS
# ============================================================

def display_analysis(
    analysis_result
):

    print("\n" + "=" * 60)

    print(
        "TRUSTLENS - EVIDENCE ASSESSMENT"
    )

    print("=" * 60)

    if not analysis_result.get("success"):

        print(
            "\nAnalysis could not be generated."
        )

        print(
            analysis_result.get(
                "error",
                "Unknown error."
            )
        )

        return

    analysis = analysis_result.get(
        "analysis",
        {}
    )

    # --------------------------------------------------------
    # COMPANY
    # --------------------------------------------------------

    company = analysis.get(
        "company",
        "Unknown"
    )

    print(
        f"\nCompany: {company}"
    )

    # --------------------------------------------------------
    # TRUST SCORE
    # --------------------------------------------------------

    trust_score = analysis.get(
        "trust_score",
        "N/A"
    )

    assessment = analysis.get(
        "assessment",
        "inconclusive"
    )

    confidence = analysis.get(
        "confidence",
        "low"
    )

    print(
        f"Evidence Score: {trust_score}/100"
    )

    print(
        f"Assessment: {assessment}"
    )

    print(
        f"Confidence: {confidence}"
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    summary = analysis.get(
        "summary"
    )

    if summary:

        print(
            "\n" + "-" * 60
        )

        print(
            "SUMMARY"
        )

        print(
            "-" * 60
        )

        print(
            summary
        )

    # --------------------------------------------------------
    # POSITIVE SIGNALS
    # --------------------------------------------------------

    positive_signals = analysis.get(
        "positive_signals",
        []
    )

    if positive_signals:

        print(
            "\n" + "-" * 60
        )

        print(
            "POSITIVE EVIDENCE"
        )

        print(
            "-" * 60
        )

        for item in positive_signals:

            signal = item.get(
                "signal",
                ""
            )

            source = item.get(
                "source",
                ""
            )

            evidence = item.get(
                "evidence",
                ""
            )

            print(
                f"\n✓ {signal}"
            )

            if source:

                print(
                    f"  Source: {source}"
                )

            if evidence:

                print(
                    f"  Evidence: {evidence}"
                )

    # --------------------------------------------------------
    # NEUTRAL SIGNALS
    # --------------------------------------------------------

    neutral_signals = analysis.get(
        "neutral_signals",
        []
    )

    if neutral_signals:

        print(
            "\n" + "-" * 60
        )

        print(
            "NEUTRAL / INCONCLUSIVE EVIDENCE"
        )

        print(
            "-" * 60
        )

        for item in neutral_signals:

            signal = item.get(
                "signal",
                ""
            )

            source = item.get(
                "source",
                ""
            )

            explanation = item.get(
                "explanation",
                ""
            )

            print(
                f"\n• {signal}"
            )

            if source:

                print(
                    f"  Source: {source}"
                )

            if explanation:

                print(
                    f"  Explanation: "
                    f"{explanation}"
                )

    # --------------------------------------------------------
    # RISK SIGNALS
    # --------------------------------------------------------

    risk_signals = analysis.get(
        "risk_signals",
        []
    )

    print(
        "\n" + "-" * 60
    )

    print(
        "EVIDENCE-BACKED CONCERNS"
    )

    print(
        "-" * 60
    )

    if risk_signals:

        for item in risk_signals:

            signal = item.get(
                "signal",
                ""
            )

            source = item.get(
                "source",
                ""
            )

            evidence = item.get(
                "evidence",
                ""
            )

            print(
                f"\n⚠ {signal}"
            )

            if source:

                print(
                    f"  Source: {source}"
                )

            if evidence:

                print(
                    f"  Evidence: {evidence}"
                )

    else:

        print(
            "\nNo specific evidence-backed "
            "concerns were identified from "
            "the collected evidence."
        )

    # --------------------------------------------------------
    # MISSING INFORMATION
    # --------------------------------------------------------

    missing_information = analysis.get(
        "missing_information",
        []
    )

    if missing_information:

        print(
            "\n" + "-" * 60
        )

        print(
            "LIMITATIONS / INFORMATION NOT OBSERVED"
        )

        print(
            "-" * 60
        )

        for item in missing_information:

            print(
                f"\n• {item}"
            )

    # --------------------------------------------------------
    # EVIDENCE TRAIL
    # --------------------------------------------------------

    evidence_trail = analysis.get(
        "evidence_trail",
        []
    )

    if evidence_trail:

        print(
            "\n" + "-" * 60
        )

        print(
            "EVIDENCE TRAIL"
        )

        print(
            "-" * 60
        )

        for item in evidence_trail:

            claim = item.get(
                "claim",
                ""
            )

            source = item.get(
                "source",
                ""
            )

            strength = item.get(
                "strength",
                "low"
            )

            print(
                f"\n• Claim: {claim}"
            )

            print(
                f"  Source: {source}"
            )

            print(
                f"  Strength: {strength}"
            )

    # --------------------------------------------------------
    # REASONING
    # --------------------------------------------------------

    reasoning = analysis.get(
        "reasoning"
    )

    if reasoning:

        print(
            "\n" + "-" * 60
        )

        print(
            "ASSESSMENT REASONING"
        )

        print(
            "-" * 60
        )

        print(
            reasoning
        )


# ============================================================
# SAVE RESULTS
# ============================================================

def save_results(
    domain,
    evidence_packet,
    analysis_result
):

    try:

        safe_domain = (
            domain
            .replace(".", "_")
            .replace("/", "_")
        )

        filename = (
            f"trustlens_{safe_domain}.json"
        )

        output = {

            "company_domain":
                domain,

            "evidence_packet":
                evidence_packet,

            "analysis":
                analysis_result
        }

        with open(
            filename,
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(

                output,

                file,

                indent=2,

                ensure_ascii=False,

                default=str
            )

        print(
            f"\n✓ Full results saved to: "
            f"{filename}"
        )

    except Exception as error:

        print(
            f"\n⚠ Could not save results: "
            f"{error}"
        )


# ============================================================
# MAIN TRUSTLENS PIPELINE
# ============================================================

def run_trustlens(user_input):

    # Accepts a domain (stripe.com) or a company name (Stripe)

    resolution = resolve_company_domain(
        user_input
    )

    if not resolution["success"]:

        print(
            f"\n{resolution['error']}"
        )

        return

    domain = resolution["domain"]

    print_header()

    if resolution.get("resolved"):

        print(
            f"\nResolved '{user_input.strip()}' "
            f"-> {domain}"
        )

    print(
        f"\nTarget company domain: {domain}"
    )

    # ========================================================
    # STEP 1 — WHOIS
    # ========================================================

    whois_result = run_whois(
        domain
    )

    # ========================================================
    # STEP 2 — WEBSITE
    # ========================================================

    website_result = run_website(
        domain
    )

    # ========================================================
    # STEP 3 — GITHUB
    # ========================================================

    github_result = run_github(
        domain
    )

    # ========================================================
    # STEP 4 — TAVILY
    # ========================================================

    tavily_result = run_tavily(
        domain
    )

    # ========================================================
    # STEP 5 — NORMALIZE EVIDENCE
    # ========================================================

    evidence_packet = (
        run_evidence_normalization(

            domain,

            whois_result,

            website_result,

            github_result,

            tavily_result
        )
    )

    # ========================================================
    # STEP 6 — MISTRAL REASONING
    # ========================================================

    analysis_result = (
        run_mistral_analysis(
            evidence_packet
        )
    )

    # ========================================================
    # DISPLAY RESULT
    # ========================================================

    display_analysis(
        analysis_result
    )

    # ========================================================
    # SAVE RESULT
    # ========================================================

    save_results(

        domain,

        evidence_packet,

        analysis_result
    )


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    user_input = input(
        "\nEnter company name or domain: "
    )

    run_trustlens(
        user_input
    )