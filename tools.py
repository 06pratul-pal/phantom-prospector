"""
tools.py — Phantom Prospector Tool Implementations
Uses OpenAI's built-in web search + BeautifulSoup for email extraction
"""

import re
import json
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os
from openai import OpenAI

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


# ─── Tool 1: Web Search via OpenAI ───────────────────────────────────────────

def web_search_tool(query: str, num_results: int = 5) -> list:
    """
    Search using OpenAI's built-in web search tool (responses API).
    Falls back to googlesearch if needed.
    """
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=f"Search for: {query}. Return a list of up to {num_results} relevant results with their title, URL, and a brief description. Format as JSON array with fields: title, url, snippet."
        )

        # Extract text from response
        result_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for block in item.content:
                    if hasattr(block, "text"):
                        result_text += block.text

        # Try to parse JSON from response
        json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if json_match:
            results = json.loads(json_match.group(0))
            return results[:num_results]

        # If no JSON, extract URLs from text and build results
        urls = re.findall(r'https?://[^\s\)\]\|"\'<>]+', result_text)
        results = []
        for url in urls[:num_results]:
            url = url.rstrip('.,;')
            results.append({"title": url, "url": url, "snippet": ""})
        return results

    except Exception as e:
        # Fallback: try googlesearch
        return _googlesearch_fallback(query, num_results)


def _googlesearch_fallback(query: str, num_results: int = 5) -> list:
    """Fallback using googlesearch-python library."""
    results = []
    try:
        from googlesearch import search
        urls = list(search(query, num_results=num_results, sleep_interval=2))
        for url in urls:
            try:
                resp = requests.get(url, headers=HEADERS, timeout=6)
                soup = BeautifulSoup(resp.text, "html.parser")
                title = (soup.title.string or url).strip()[:100] if soup.title else url
                meta = soup.find("meta", attrs={"name": "description"})
                snippet = meta["content"][:200] if meta and meta.get("content") else ""
                results.append({"title": title, "url": url, "snippet": snippet})
                time.sleep(0.5)
            except Exception:
                results.append({"title": url, "url": url, "snippet": ""})
    except Exception:
        pass
    return results


# ─── Tool 2: Email Extractor ──────────────────────────────────────────────────

def extract_emails_tool(url: str) -> dict:
    """
    Visit a webpage and extract emails, company name, contact person.
    Also checks /contact and /about subpages.
    """
    result = {
        "url": url,
        "emails": [],
        "company_name": "",
        "contact_name": "",
        "phones": [],
        "success": False
    }

    all_emails = []

    pages_to_check = [url]
    # Add contact/about subpages
    base = url.rstrip("/")
    pages_to_check += [f"{base}/contact", f"{base}/contact-us", f"{base}/about"]

    for page_url in pages_to_check:
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=7)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            text = resp.text

            # Emails from mailto links
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0].strip().lower()
                    if email and "@" in email:
                        all_emails.append(email)

            # Emails from text
            email_pattern = r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
            text_emails = re.findall(email_pattern, text)
            all_emails.extend([e.lower() for e in text_emails])

            # Company name (from main page only)
            if page_url == url and not result["company_name"]:
                og_name = soup.find("meta", property="og:site_name")
                if og_name and og_name.get("content"):
                    result["company_name"] = og_name["content"].strip()
                elif soup.title:
                    result["company_name"] = (soup.title.string or "").split("|")[0].split("–")[0].strip()[:80]

            # Contact name heuristic
            if not result["contact_name"]:
                for tag in soup.find_all(["h1", "h2", "h3", "strong"]):
                    txt = tag.get_text(strip=True)
                    words = txt.split()
                    if 2 <= len(words) <= 3 and all(w[0].isupper() for w in words if w):
                        skip_words = ["home", "about", "contact", "service", "blog",
                                      "pricing", "company", "team", "our", "the", "get", "why"]
                        if not any(kw in txt.lower() for kw in skip_words):
                            result["contact_name"] = txt
                            break

            # Phone
            phone_pattern = r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{3,5}[-\s\.]?[0-9]{4,10}'
            phones = re.findall(phone_pattern, text)
            result["phones"] = list(set(result["phones"] + phones))[:3]

        except Exception:
            continue

    # Clean up emails
    junk_domains = {
        "example.com", "sentry.io", "wixpress.com", "w3.org", "schema.org",
        "google.com", "facebook.com", "twitter.com", "placeholder.com",
        "youremail.com", "email.com", "domain.com", "company.com",
        "wordpress.com", "gravatar.com", "amazonaws.com"
    }
    clean_emails = []
    seen = set()
    for e in all_emails:
        domain = e.split("@")[-1]
        if (domain not in junk_domains and e not in seen
                and len(e) < 80 and "." in domain):
            clean_emails.append(e)
            seen.add(e)

    result["emails"] = clean_emails[:5]
    result["success"] = bool(clean_emails)
    return result


# ─── Tool 3: Lead Qualifier ───────────────────────────────────────────────────

def qualify_lead_tool(company_name: str, url: str, snippet: str, target_criteria: str) -> dict:
    """Score a lead 1-10 based on relevance to target criteria."""
    score = 5
    reasoning_parts = []

    combined_text = f"{company_name} {url} {snippet}".lower()
    criteria_lower = target_criteria.lower()
    criteria_words = re.findall(r'\b\w{4,}\b', criteria_lower)

    # Keyword matches
    matches = sum(1 for w in criteria_words if w in combined_text)
    keyword_boost = min(matches, 3)
    score += keyword_boost
    if keyword_boost > 0:
        reasoning_parts.append(f"{matches} keyword matches")

    # URL quality
    domain = urlparse(url).netloc.lower()
    if any(s in domain for s in ["linkedin", "linkedin.com"]):
        score += 1
        reasoning_parts.append("LinkedIn profile")
    if any(s in domain for s in ["facebook", "twitter", "instagram", "youtube", "reddit", "quora"]):
        score -= 2
        reasoning_parts.append("social/forum page")
    if any(s in domain for s in ["justdial", "sulekha", "indiamart", "yellowpages"]):
        score -= 1
        reasoning_parts.append("directory listing")

    # Snippet signals
    snippet_lower = snippet.lower()
    if any(w in snippet_lower for w in ["ceo", "founder", "director", "owner", "co-founder"]):
        score += 1
        reasoning_parts.append("decision maker")
    if any(w in snippet_lower for w in ["hiring", "looking for", "we need", "seeking"]):
        score += 1
        reasoning_parts.append("hiring signal")
    if len(snippet) > 80:
        score += 0.5

    score = max(1, min(10, round(score)))
    return {
        "score": score,
        "reasoning": "; ".join(reasoning_parts) if reasoning_parts else "keyword and URL analysis",
        "company_name": company_name,
        "url": url
    }


# ─── Tool 4: Outreach Writer ──────────────────────────────────────────────────

def write_outreach_tool(company_name: str, contact_name: str, email: str,
                        what_they_do: str, sender_context: str) -> dict:
    """Write a personalized cold outreach email."""

    first_name = contact_name.split()[0] if contact_name else ""
    greeting = f"Hi {first_name}," if first_name else f"Hi {company_name} team,"

    sender_lower = sender_context.lower()
    if any(w in sender_lower for w in ["automation", "ai", "agent", "bot"]):
        service = "AI automation"
        value_prop = "save 10+ hours per week by automating repetitive workflows"
    elif any(w in sender_lower for w in ["developer", "dev", "engineer"]):
        service = "custom software development"
        value_prop = "build scalable tech solutions tailored to your needs"
    elif any(w in sender_lower for w in ["marketing", "seo", "content"]):
        service = "digital marketing"
        value_prop = "grow online presence and generate more qualified leads"
    elif any(w in sender_lower for w in ["design", "ui", "ux"]):
        service = "UI/UX design"
        value_prop = "create interfaces that convert visitors into customers"
    else:
        service = "consulting services"
        value_prop = "help streamline operations and scale efficiently"

    what_clean = (what_they_do or f"what {company_name} does")[:100].lower().rstrip(".")

    message = f"""{greeting}

I came across {company_name} and was genuinely impressed by your work in {what_clean}.

I specialize in {service}, and I think there's a real opportunity to {value_prop} for a business like yours — without major disruption to what's already working.

I'd love to share 2-3 specific ideas I have for {company_name}. No lengthy pitch — just a focused 15-minute call to see if there's a fit.

Would you be open to a quick chat this week?

Best,
{sender_context.split(',')[0].strip().title()}

P.S. Happy to send a short case study of similar results if helpful."""

    return {
        "message": message,
        "subject": f"Quick idea for {company_name}",
        "to": email,
        "company_name": company_name
    }
