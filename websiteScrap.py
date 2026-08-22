import requests

from bs4 import BeautifulSoup

from urllib.parse import (
    urljoin,
    urlparse,
    urldefrag
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}


TIMEOUT = 10


PAGE_PATTERNS = {

    "about": [
        "about",
        "about-us",
        "company",
        "our-story",
        "story"
    ],

    "team": [
        "team",
        "people",
        "leadership",
        "founders",
        "management"
    ],

    "contact": [
        "contact",
        "contact-us",
        "get-in-touch",
        "support",
        "locations"
    ]
}


COMMON_PATHS = {

    "about": [
        "/about",
        "/about-us",
        "/company",
        "/our-story"
    ],

    "team": [
        "/team",
        "/people",
        "/leadership",
        "/founders"
    ],

    "contact": [
        "/contact",
        "/contact-us",
        "/support"
    ]
}


SOCIAL_DOMAINS = [
    "linkedin.com",
    "twitter.com",
    "x.com",
    "github.com",
    "facebook.com",
    "instagram.com",
    "youtube.com"
]


def normalize_url(url):

    url = url.strip()

    if not url.startswith(
        ("https://", "http://")
    ):

        url = "https://" + url

    return url.rstrip("/")


def get_page(url):

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        return {

            "success": response.ok,

            "status_code": response.status_code,

            "url": response.url,

            "html": response.text
        }

    except requests.RequestException as error:

        return {

            "success": False,

            "url": url,

            "error": str(error),

            "html": None
        }


def clean_url(url):

    clean, _ = urldefrag(url)

    return clean.rstrip("/")


def is_internal(url, base_url):

    return (
        urlparse(url).netloc ==
        urlparse(base_url).netloc
    )


def extract_visible_text(soup):

    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "iframe"
    ]):

        tag.decompose()

    return soup.get_text(
        separator=" ",
        strip=True
    )


def get_internal_links(soup, base_url):

    links = set()

    for tag in soup.find_all(
        "a",
        href=True
    ):

        href = tag["href"].strip()

        if not href:
            continue

        full_url = clean_url(
            urljoin(
                base_url,
                href
            )
        )

        if is_internal(
            full_url,
            base_url
        ):

            links.add(full_url)

    return sorted(list(links))


def discover_page(
    soup,
    base_url,
    page_type
):

    patterns = PAGE_PATTERNS[page_type]

    for tag in soup.find_all(
        "a",
        href=True
    ):

        href = tag["href"]

        text = tag.get_text(
            " ",
            strip=True
        )

        combined = (
            text.lower() +
            " " +
            href.lower()
        )

        if any(
            pattern in combined
            for pattern in patterns
        ):

            full_url = clean_url(
                urljoin(
                    base_url,
                    href
                )
            )

            if is_internal(
                full_url,
                base_url
            ):

                return full_url

    return None


def fetch_important_page(
    soup,
    base_url,
    page_type
):

    discovered_url = discover_page(
        soup,
        base_url,
        page_type
    )

    # Try discovered URL first

    if discovered_url:

        result = get_page(
            discovered_url
        )

        if result["success"]:

            page_soup = BeautifulSoup(
                result["html"],
                "html.parser"
            )

            text = extract_visible_text(
                page_soup
            )

            return {

                "status": "found",

                "url": result["url"],

                "method": "homepage_link",

                "text_length": len(text),

                "text_preview": text[:1200]
            }

    # Try common paths

    for path in COMMON_PATHS[page_type]:

        test_url = (
            base_url.rstrip("/") +
            path
        )

        result = get_page(test_url)

        if result["success"]:

            page_soup = BeautifulSoup(
                result["html"],
                "html.parser"
            )

            text = extract_visible_text(
                page_soup
            )

            return {

                "status": "found",

                "url": result["url"],

                "method": "common_path",

                "text_length": len(text),

                "text_preview": text[:1200]
            }

    return {

        "status": "not_discovered",

        "url": None,

        "method": (
            "homepage_links_and_common_paths"
        ),

        "note": (
            "The collector did not discover this page. "
            "This does not prove that the page does not exist."
        )
    }


def find_social_links(soup):

    links = set()

    for tag in soup.find_all(
        "a",
        href=True
    ):

        href = tag["href"].strip()

        if any(
            domain in href.lower()
            for domain in SOCIAL_DOMAINS
        ):

            links.add(href)

    return sorted(list(links))


def extract_address(soup):

    address_tag = soup.find("address")

    if address_tag:

        address = address_tag.get_text(
            " ",
            strip=True
        )

        if address:

            return address

    return None


def calculate_website_signals(
    homepage_text,
    pages,
    social_links,
    address
):
    """
    Generate deterministic website evidence signals.
    """

    signals = []

    # Content depth

    if len(homepage_text) > 1500:

        signals.append({
            "signal": "substantial_public_content",
            "level": "positive",
            "reason": (
                "The collected homepage contains "
                "substantial textual content."
            )
        })

    elif len(homepage_text) > 300:

        signals.append({
            "signal": "basic_public_content",
            "level": "neutral",
            "reason": (
                "The homepage contains some "
                "publicly accessible content."
            )
        })

    else:

        signals.append({
            "signal": "limited_homepage_content",
            "level": "neutral",
            "reason": (
                "The collected homepage contains "
                "limited text. This may reflect a "
                "minimal or JavaScript-driven design."
            )
        })

    # Important pages

    found_pages = [
        page_name
        for page_name, data in pages.items()
        if data["status"] == "found"
    ]

    if len(found_pages) >= 2:

        signals.append({
            "signal": "multiple_corporate_pages",
            "level": "positive",
            "reason": (
                f"The collector found multiple "
                f"corporate-information pages: "
                f"{', '.join(found_pages)}."
            )
        })

    elif len(found_pages) == 1:

        signals.append({
            "signal": "corporate_information_page",
            "level": "positive",
            "reason": (
                f"The collector found a "
                f"{found_pages[0]} page."
            )
        })

    # Social presence

    if len(social_links) >= 3:

        signals.append({
            "signal": "multiple_social_links",
            "level": "positive",
            "reason": (
                f"{len(social_links)} social links "
                f"were observed on the homepage."
            )
        })

    elif len(social_links) > 0:

        signals.append({
            "signal": "social_presence_observed",
            "level": "neutral",
            "reason": (
                "At least one social link was observed."
            )
        })

    # Address

    if address:

        signals.append({
            "signal": "address_observed",
            "level": "neutral",
            "reason": (
                "An address element was found, but it "
                "has not been independently verified."
            )
        })

    return signals


def scrape_company_website(url):

    url = normalize_url(url)

    print(f"\n🌐 Scraping: {url}")

    homepage_result = get_page(url)

    if not homepage_result["success"]:

        return {

            "success": False,

            "website": url,

            "error": homepage_result.get(
                "error",
                "Homepage could not be collected."
            )
        }

    final_url = (
        homepage_result["url"]
        .rstrip("/")
    )

    soup = BeautifulSoup(
        homepage_result["html"],
        "html.parser"
    )

    homepage_text = extract_visible_text(
        soup
    )

    title = (
        soup.title.get_text(strip=True)
        if soup.title
        else None
    )

    internal_links = get_internal_links(
        soup,
        final_url
    )

    pages = {

        "about": fetch_important_page(
            soup,
            final_url,
            "about"
        ),

        "team": fetch_important_page(
            soup,
            final_url,
            "team"
        ),

        "contact": fetch_important_page(
            soup,
            final_url,
            "contact"
        )
    }

    social_links = find_social_links(
        soup
    )

    address = extract_address(
        soup
    )

    derived_signals = (
        calculate_website_signals(
            homepage_text,
            pages,
            social_links,
            address
        )
    )

    return {

        "success": True,

        "website": final_url,

        "homepage": {

            "title": title,

            "text_length":
                len(homepage_text),

            "text_preview":
                homepage_text[:2000],

            "internal_links_count":
                len(internal_links)
        },

        "important_pages": pages,

        "social_presence": {

            "count": len(social_links),

            "links": social_links,

            "collection_scope":
                "homepage_only"
        },

        "address": {

            "value": address,

            "verified": False
        },

        "derived_signals":
            derived_signals,

        "limitations": [

            "JavaScript-rendered content may not be collected.",

            "Only the homepage and selected important "
            "pages were checked.",

            "A page not discovered by the collector "
            "may still exist.",

            "Social links and addresses are not "
            "independently verified."
        ]
    }


if __name__ == "__main__":

    website = input(
        "Enter company website: "
    )

    result = scrape_company_website(
        website
    )

    print("\n" + "=" * 60)
    print("WEBSITE EVIDENCE")
    print("=" * 60)

    print(result)