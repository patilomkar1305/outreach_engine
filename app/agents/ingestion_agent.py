"""
app/agents/ingestion_agent.py
─────────────────────────────
STAGE 1 – Ingestion  (ephemeral)

Responsibilities:
  • Accept whatever the user gave us (LinkedIn URL, plain text, PDF, DOC file).
  • If it's a URL → fetch the page and extract visible text.
  • If it's a file path → extract text from PDF/DOC.
  • Normalise everything into a structured payload that the persona agent
    can consume.
  • Compute the opaque target_hash so we never store the raw identifier.

Nothing here touches the LLM.  It's pure data-wrangling.
"""

from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.graph.state import OutreachState, start_stage, complete_stage
from app.utils.sanitizer import compute_target_hash

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_url(text: str) -> bool:
    """Rough check: does this look like a URL?"""
    try:
        result = urlparse(text.strip())
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def _is_file_path(text: str) -> bool:
    """Check if text looks like a file path (PDF/DOC)."""
    text = text.strip()
    return text.endswith(('.pdf', '.docx', '.doc')) and (Path(text).exists() if not text.startswith('http') else False)


def _extract_text_from_pdf(file_path: str) -> str:
    """Extract text content from PDF file."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        extracted = "\n".join(text_parts)
        logger.info("Extracted %d chars from PDF: %s", len(extracted), file_path)
        return extracted
    except Exception as exc:
        logger.error("Failed to extract PDF %s: %s", file_path, exc)
        return ""


def _extract_text_from_docx(file_path: str) -> str:
    """Extract text content from DOCX file."""
    try:
        from docx import Document
        doc = Document(file_path)
        text_parts = [para.text for para in doc.paragraphs if para.text.strip()]
        extracted = "\n".join(text_parts)
        logger.info("Extracted %d chars from DOCX: %s", len(extracted), file_path)
        return extracted
    except Exception as exc:
        logger.error("Failed to extract DOCX %s: %s", file_path, exc)
        return ""


def _fetch_and_extract(url: str, timeout: int = 10) -> str:
    """
    Download a page and return its visible text (no HTML tags).
    Falls back to an empty string on any network error so the pipeline
    can continue with whatever else the user provided.
    """
    try:
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": (
                "Mozilla/5.0 (compatible; OutreachEngine/1.0)"
            )
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Strip scripts / styles
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        logger.info("Fetched %d chars from %s", len(text), url)
        return text
    except Exception as exc:
        logger.warning("Could not fetch %s: %s", url, exc)
        return ""


def _extract_links(raw: str) -> dict[str, str]:
    """Pull out any URLs that look like known profile / company links."""
    link_map: dict[str, str] = {}
    url_pattern = re.compile(r"https?://[^\s<>\"']+")

    for match in url_pattern.finditer(raw):
        url = match.group(0).rstrip(".,;)")
        lower = url.lower()
        if "linkedin.com" in lower:
            link_map.setdefault("linkedin", url)
        elif "twitter.com" in lower or "x.com" in lower:
            link_map.setdefault("twitter", url)
        elif "github.com" in lower:
            link_map.setdefault("github", url)
        else:
            link_map.setdefault("website", url)
    return link_map


def _extract_name(text: str) -> str:
    """
    Extract the person's full name from the profile text.
    Looks for common patterns like the very first line being a name,
    or "Name: X" patterns.
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""

    # Pattern 1: First line is often the name (Title Case, 2-4 words, no special chars)
    first_line = lines[0].strip()
    # Remove common prefixes
    for prefix in ["Name:", "Full Name:", "Profile:"]:
        if first_line.lower().startswith(prefix.lower()):
            first_line = first_line[len(prefix):].strip()
            break

    # Check if first line looks like a name (2-4 Title Case words, letters/hyphens only)
    name_match = re.match(r'^([A-Z][a-z]+(?:[\s\-][A-Z][a-z]+){0,3})$', first_line)
    if name_match:
        return name_match.group(1)

    # Pattern 2: Look for "I'm <Name>" or "My name is <Name>"
    im_match = re.search(r"(?:I'm|I am|My name is|Hi,? I'm)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})", text)
    if im_match:
        return im_match.group(1)

    # Pattern 3: Look for a Title-Case name near role/title keywords
    # e.g. "Sarah Chen, VP of Engineering" or "Sarah Chen - VP"
    name_role_match = re.search(
        r'([A-Z][a-z]+(?:\s[A-Z][a-z]+){0,2})\s*[,\-–|]\s*(?:CEO|CTO|VP|Director|Manager|Engineer|Founder|Head|Chief|President|Lead)',
        text
    )
    if name_role_match:
        return name_role_match.group(1)

    # Pattern 4: First line might be name even without strict regex
    # Check if it's short (< 40 chars) and doesn't look like a sentence
    if len(first_line) < 40 and not any(c in first_line for c in '.!?:@#$%'):
        words = first_line.split()
        if 1 < len(words) <= 4 and all(w[0].isupper() for w in words if w):
            return first_line

    return ""


def _extract_full_role(text: str) -> str:
    """
    Extract the full job title (e.g. 'VP of Engineering') not just 'VP'.
    """
    # Pattern: "<Title> of/at/for <Dept>" or "<Title>, <Company>"
    role_patterns = [
        r'((?:Chief|Senior|Junior|Lead|Staff|Principal|Head)?\s*(?:VP|Vice President|Director|Manager|Engineer|Founder|Co-Founder|CEO|CTO|CFO|COO|CMO|CIO|CISO)\s*(?:of\s+[A-Za-z\s&]+?)?(?=\s*(?:at|@|,|\||\n|$)))',
        r'((?:Senior|Junior|Lead|Staff|Principal)?\s*(?:Software|Data|Product|Project|Marketing|Sales|DevOps|Platform|Cloud|Full[- ]?Stack|Backend|Frontend|Solutions|Systems)\s*(?:Engineer|Developer|Architect|Scientist|Analyst|Manager|Designer|Consultant))',
    ]
    for pattern in role_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _guess_company_role(text: str) -> tuple[str, str, str, str]:
    """
    Very lightweight extraction of company / role / industry / name from text.
    In a production system you'd run a dedicated NER model here.
    Returns (company, role, industry, name) – any can be empty string.
    """
    company = role = industry = ""
    name = _extract_name(text)

    # Role heuristics - try full role first, then fall back to simple title
    role = _extract_full_role(text)
    if not role:
        role_titles = [
            "CEO", "CTO", "VP of Engineering", "VP", "Director", "Manager", "Engineer",
            "Founder", "Co-Founder", "Product Manager", "Designer",
            "Developer", "Data Scientist", "Analyst", "Consultant",
        ]
        text_lower = text.lower()
        for title in role_titles:
            if title.lower() in text_lower:
                role = title
                break

    # Industry keywords (expand as needed)
    industries = {
        "tech": ["software", "saas", "ai", "machine learning", "cloud", "cybersecurity", "kubernetes", "devops", "infrastructure"],
        "finance": ["fintech", "banking", "investment", "crypto", "insurance"],
        "health": ["healthtech", "biotech", "pharma", "medical", "wellness"],
        "education": ["edtech", "education", "learning", "university"],
        "marketing": ["marketing", "advertising", "brand", "growth"],
        "design": ["design", "ux", "ui", "product design"],
    }
    text_lower = text.lower()
    for ind, keywords in industries.items():
        if any(kw in text_lower for kw in keywords):
            industry = ind
            break

    # Company – look for "at <Company>" or "Company: <name>" patterns
    at_match = re.search(r"\bat\s+([A-Z][A-Za-z0-9\s&\.]{2,30})", text)
    if at_match:
        company = at_match.group(1).strip()

    return company, role, industry, name


# ---------------------------------------------------------------------------
# Node function  –  called by LangGraph
# ---------------------------------------------------------------------------

def ingestion_node(state: OutreachState) -> OutreachState:
    """
    Entry node.  Expects `state["raw_input"]` to be set by the caller.
    Can handle: URLs, plain text, PDF file paths, DOCX file paths.
    """
    raw_input: str = state.get("raw_input", "")
    if not raw_input:
        raise ValueError("ingestion_node: raw_input is empty – nothing to ingest.")

    logger.info("=== INGESTION START ===")
    
    # Start stage tracking
    state = start_stage(state, "ingestion")

    # ── 1. Determine input type and extract text ─────────────────────
    lines = [line.strip() for line in raw_input.splitlines() if line.strip()]
    extracted_texts: list[str] = []
    all_links: dict[str, str] = {}

    for line in lines:
        if _is_url(line):
            # URL - fetch web content
            text = _fetch_and_extract(line)
            extracted_texts.append(text)
            all_links.update(_extract_links(line))  # the URL itself
            all_links.update(_extract_links(text))  # any links inside the page
        elif _is_file_path(line):
            # File path - extract from PDF/DOC
            if line.endswith('.pdf'):
                text = _extract_text_from_pdf(line)
            elif line.endswith(('.docx', '.doc')):
                text = _extract_text_from_docx(line)
            else:
                text = ""
            extracted_texts.append(text)
            all_links.update(_extract_links(text))
        else:
            # Plain text
            extracted_texts.append(line)
            all_links.update(_extract_links(line))

    combined_text = "\n".join(extracted_texts)

    # ── 2. Guess structured fields ────────────────────────────────────
    company, role, industry, name = _guess_company_role(combined_text)

    # ── 3. Compute opaque hash ────────────────────────────────────────
    # Use the first URL if available, else the whole raw input
    identifier = lines[0] if lines else raw_input
    target_hash = compute_target_hash(identifier)

    # Complete stage tracking
    state = complete_stage(state, "ingestion")

    # ── 4. Build updated state ────────────────────────────────────────
    updated: OutreachState = {
        **state,
        "target_identifier": identifier,
        "target_hash":       target_hash,
        "raw_profile_text":  combined_text,
        "target_name":       name,
        "company":           company,
        "role":              role,
        "industry":          industry,
        "links":             all_links,
        "status":            "ingested",
    }

    logger.info(
        "Ingestion done | name=%s company=%s role=%s industry=%s links=%s hash=%s…",
        name, company, role, industry, list(all_links.keys()), target_hash[:12],
    )
    return updated
