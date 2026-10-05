import os
import json
import re

from dotenv import load_dotenv
from mistralai import Mistral


# ============================================================
# ENVIRONMENT SETUP
# ============================================================

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

if not MISTRAL_API_KEY:
    raise ValueError(
        "MISTRAL_API_KEY not found. "
        "Add it to your .env file."
    )


client = Mistral(
    api_key=MISTRAL_API_KEY
)


MODEL = "ministral-14b-2512"


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):
    """
    Extract valid JSON from the LLM response.

    Handles:
    - Direct JSON
    - ```json code fences
    - ``` code fences
    - Extra text around a JSON object
    """

    if not text:
        raise ValueError(
            "Empty response received from Mistral."
        )

    text = text.strip()

    # --------------------------------------------------------
    # Try direct JSON
    # --------------------------------------------------------

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Remove markdown code fences
    # --------------------------------------------------------

    cleaned_text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    cleaned_text = re.sub(
        r"^```\s*",
        "",
        cleaned_text
    )

    cleaned_text = re.sub(
        r"\s*```$",
        "",
        cleaned_text
    )

    try:
        return json.loads(
            cleaned_text.strip()
        )

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # Find JSON object
    # --------------------------------------------------------

    start = cleaned_text.find("{")
    end = cleaned_text.rfind("}")

    if start != -1 and end != -1:

        possible_json = (
            cleaned_text[start:end + 1]
        )

        try:
            return json.loads(
                possible_json
            )

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Could not extract valid JSON "
        "from Mistral response."
    )


# ============================================================
# OUTPUT CLEANUP
# ============================================================

def clean_list(value):
    """
    Ensure a value is always a list.
    """

    if isinstance(value, list):
        return value

    return []


def clean_string(value, default=""):
    """
    Ensure a value is always a string.
    """

    if value is None:
        return default

    return str(value).strip()


# ============================================================
# ANALYSIS VALIDATION
# ============================================================

def validate_analysis(analysis):
    """
    Normalize and validate the LLM output.

    This prevents malformed responses from
    breaking the rest of TrustLens.
    """

    if not isinstance(analysis, dict):

        raise ValueError(
            "Mistral returned an invalid analysis format."
        )

    # --------------------------------------------------------
    # TRUST SCORE
    # --------------------------------------------------------

    trust_score = analysis.get(
        "trust_score",
        50
    )

    try:

        trust_score = int(
            round(float(trust_score))
        )

    except Exception:

        trust_score = 50

    trust_score = max(
        0,
        min(100, trust_score)
    )

    # --------------------------------------------------------
    # ASSESSMENT
    # --------------------------------------------------------

    allowed_assessments = [

        "strong_evidence_of_real_operation",

        "likely_real_but_limited_evidence",

        "inconclusive",

        "evidence_backed_concerns"
    ]

    assessment = clean_string(
        analysis.get(
            "assessment"
        ),
        "inconclusive"
    )

    if assessment not in allowed_assessments:

        assessment = "inconclusive"

    # --------------------------------------------------------
    # CONFIDENCE
    # --------------------------------------------------------

    allowed_confidence = [

        "high",

        "medium",

        "low"
    ]

    confidence = clean_string(
        analysis.get(
            "confidence"
        ),
        "low"
    ).lower()

    if confidence not in allowed_confidence:

        confidence = "low"

    # --------------------------------------------------------
    # CLEAN SIGNAL LISTS
    # --------------------------------------------------------

    positive_signals = clean_list(
        analysis.get(
            "positive_signals"
        )
    )

    neutral_signals = clean_list(
        analysis.get(
            "neutral_signals"
        )
    )

    risk_signals = clean_list(
        analysis.get(
            "risk_signals"
        )
    )

    missing_information = clean_list(
        analysis.get(
            "missing_information"
        )
    )

    evidence_trail = clean_list(
        analysis.get(
            "evidence_trail"
        )
    )

    # --------------------------------------------------------
    # CLEAN EVIDENCE TRAIL
    # --------------------------------------------------------

    cleaned_evidence_trail = []

    for item in evidence_trail:

        if not isinstance(item, dict):
            continue

        strength = clean_string(
            item.get(
                "strength"
            ),
            "low"
        ).lower()

        if strength not in [
            "high",
            "medium",
            "low"
        ]:

            strength = "low"

        cleaned_evidence_trail.append({

            "claim": clean_string(
                item.get(
                    "claim"
                )
            ),

            "source": clean_string(
                item.get(
                    "source"
                )
            ),

            "strength": strength
        })

    # --------------------------------------------------------
    # RETURN CLEAN ANALYSIS
    # --------------------------------------------------------

    return {

        "company": clean_string(
            analysis.get(
                "company"
            )
        ),

        "trust_score": trust_score,

        "assessment": assessment,

        "confidence": confidence,

        "summary": clean_string(
            analysis.get(
                "summary"
            )
        ),

        "positive_signals": positive_signals,

        "neutral_signals": neutral_signals,

        "risk_signals": risk_signals,

        "missing_information": missing_information,

        "evidence_trail":
            cleaned_evidence_trail,

        "reasoning": clean_string(
            analysis.get(
                "reasoning"
            )
        )
    }


# ============================================================
# PROMPT
# ============================================================

def build_reasoning_prompt(
    evidence_packet
):
    """
    Build the prompt for the TrustLens
    evidence reasoning layer.
    """

    evidence_json = json.dumps(
        evidence_packet,
        indent=2,
        default=str,
        ensure_ascii=False
    )

    return f"""
You are the reasoning engine for TrustLens,
an evidence-based company due-diligence system.

Your task is NOT to decide whether a company is
"good" or "bad".

Your task is to evaluate the STRENGTH,
CONSISTENCY, and CORROBORATION of the evidence
that was collected.

You must reason conservatively.

============================================================
CORE PRINCIPLE
============================================================

ABSENCE OF EVIDENCE IS NOT EVIDENCE OF FRAUD.

A collector not finding something does NOT prove
that the company does not have it.

For example:

- No Team page found by the scraper does not mean
  the company has no team.

- No physical address extracted does not mean
  the company has no physical location.

- No GitHub organization found does not mean
  the company has no engineering activity.

- No funding information found does not mean
  the company is illegitimate.

- No negative news found does not mean
  the company has no risks.

- No social links found on the homepage does not
  mean the company has no social presence.

============================================================
IMPORTANT: COLLECTOR LIMITATIONS
============================================================

Do NOT convert technical collection limitations
into negative company signals.

Websites may use:

- JavaScript rendering
- client-side navigation
- redirects
- robots restrictions
- unusual URL structures
- minimal homepages
- separate corporate domains

Therefore:

"Not observed by our scraper"

is NOT equivalent to:

"The company does not have this."

When appropriate, describe such findings as:

"not observed in the collected evidence"

or:

"not independently verified from the available data"

Do NOT describe them as suspicious unless there
is actual contradictory evidence.

============================================================
SOURCE HIERARCHY
============================================================

When weighing evidence, generally use this order:

HIGHER STRENGTH:

1. Direct technical evidence
   - WHOIS data
   - verified domain information
   - GitHub organization directly linked to
     the company domain

2. Independent reputable sources
   - reputable news
   - official partner pages
   - credible funding databases

3. Official company sources
   - company website
   - official announcements

LOWER STRENGTH:

4. Search snippets
5. Social media references
6. Weakly matched sources

Official company claims are useful but should not
be treated as independently verified.

============================================================
RISK SIGNAL RULE
============================================================

ONLY create a risk signal when there is actual
evidence supporting concern.

Valid examples:

- WHOIS data directly contradicts the claimed
  company history.

- Multiple independent sources report a material
  issue.

- The company makes claims that conflict with
  independently available evidence.

- A supposedly established operation has multiple
  concrete and material inconsistencies.

INVALID examples:

- No Team page found.

- No address extracted.

- No GitHub activity.

- No funding information.

- No social links found.

- Homepage has little text.

Those are neutral or missing evidence unless
supported by additional contradictory signals.

============================================================
KNOWN / ESTABLISHED COMPANIES
============================================================

Do not reduce the assessment simply because a
collector failed to discover information about
a company.

A large or established company may have:

- a minimal homepage
- JavaScript-rendered pages
- separate corporate websites
- private repositories
- no visible social links on the homepage

Evaluate the evidence that IS available.

Do not artificially penalize strong,
consistent evidence because optional information
was not collected.

============================================================
GITHUB INTERPRETATION
============================================================

GitHub evidence is supporting evidence only.

Strong GitHub evidence can include:

- organization website matching the company domain
- strong organization name matching
- public repository activity
- recent updates
- meaningful engineering presence

However:

No public repositories is NOT suspicious.

Private repositories are invisible.

Some legitimate companies do not maintain public
open-source projects.

============================================================
TRUST SCORE MEANING
============================================================

The trust score represents:

"The strength and consistency of the collected
evidence."

It DOES NOT represent:

- probability that the company is legitimate
- probability that the company is a scam
- a financial risk rating
- a guarantee of safety

============================================================
SCORE GUIDANCE
============================================================

90-100

Very strong, consistent evidence across multiple
sources, with meaningful corroboration.

Examples:

- established domain history
- strong official identity
- independent external corroboration
- verified technical or organizational evidence
- consistent evidence across multiple collectors

75-89

Strong evidence with some limitations or gaps.

The available evidence strongly supports that the
company is a real operating organization, but not
every claim is independently verified.

55-74

Moderate evidence.

There is some positive evidence, but independent
corroboration is limited or meaningful areas
remain unclear.

35-54

Limited or inconsistent evidence.

The available evidence is insufficient for a
strong assessment, or there are material
inconsistencies.

0-34

Serious evidence-backed concerns.

Use this range ONLY when there are substantial
concrete inconsistencies or independently
supported risk signals.

DO NOT assign a low score merely because data is
missing.

============================================================
ASSESSMENT DEFINITIONS
============================================================

"strong_evidence_of_real_operation"

Use when multiple strong and reasonably consistent
signals support that the company is operating as a
real organization.

"likely_real_but_limited_evidence"

Use when positive evidence exists but independent
corroboration or available evidence is limited.

"inconclusive"

Use when the evidence is insufficient to support a
strong positive or negative conclusion.

"evidence_backed_concerns"

Use ONLY when concrete evidence supports meaningful
concerns or inconsistencies.

============================================================
OUTPUT RULES
============================================================

1. Use ONLY the evidence provided.

2. Do NOT invent facts.

3. Do NOT treat missing information as a risk
   signal by default.

4. Clearly separate:
   - positive evidence
   - neutral / inconclusive observations
   - genuine risk evidence
   - missing information

5. Every risk signal must reference actual evidence.

6. Do not repeat the same finding multiple times.

7. Keep the reasoning concise and evidence-based.

8. The evidence trail should contain the strongest
   claims supporting the final assessment.

9. If evidence sources disagree, explicitly mention
   the inconsistency.

10. If the evidence is limited, say so without
    assuming fraud.

11. Treat "not observed by the collector" differently
from "confirmed missing".

12. Do not lower the evidence score simply because
a website scraper did not discover an About, Team,
Contact, or social media page.

13. Give stronger weight to corroboration across
independent evidence sources.

14. A long-lived domain combined with an identified
organization, active external presence, reputable
third-party coverage, or verified technical activity
can collectively represent strong evidence of a
real operating company.

15. GitHub evidence should only be considered strong
when organization matching confidence is high.
A low-confidence match should not be treated as proof.

16. Do not let one collector's missing data override
strong evidence from other collectors.

Return ONLY valid JSON.

Use EXACTLY this structure:

{{
  "company": "",

  "trust_score": 0,

  "assessment": "",

  "confidence": "",

  "summary": "",

  "positive_signals": [
    {{
      "signal": "",
      "source": "",
      "evidence": ""
    }}
  ],

  "neutral_signals": [
    {{
      "signal": "",
      "source": "",
      "explanation": ""
    }}
  ],

  "risk_signals": [
    {{
      "signal": "",
      "source": "",
      "evidence": ""
    }}
  ],

  "missing_information": [
    ""
  ],

  "evidence_trail": [
    {{
      "claim": "",
      "source": "",
      "strength": "high"
    }}
  ],

  "reasoning": ""
}}

Allowed assessment values:

- "strong_evidence_of_real_operation"
- "likely_real_but_limited_evidence"
- "inconclusive"
- "evidence_backed_concerns"

Allowed confidence values:

- "high"
- "medium"
- "low"

Evidence packet:

{evidence_json}
"""


# ============================================================
# MISTRAL REASONING
# ============================================================

def analyze_evidence(
    evidence_packet
):
    """
    Send normalized evidence to Mistral
    and return structured reasoning.
    """

    try:

        prompt = build_reasoning_prompt(
            evidence_packet
        )

        response = client.chat.complete(

            model=MODEL,

            messages=[

                {
                    "role": "system",
                    "content": (
                        "You are a careful, conservative "
                        "evidence analysis system. "
                        "Never invent facts and never treat "
                        "missing information as proof of risk."
                    )
                },

                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.1
        )

        response_text = (
            response.choices[0]
            .message
            .content
        )

        analysis = extract_json(
            response_text
        )

        analysis = validate_analysis(
            analysis
        )

        return {

            "success": True,

            "analysis": analysis
        }

    except Exception as error:

        return {

            "success": False,

            "error": str(error)
        }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Mistral reasoner loaded successfully."
    )
