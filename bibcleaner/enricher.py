"""
Core enrichment logic for BibTeX entries using Semantic Scholar API.
"""

import logging
import re
import time
from typing import Dict, List, Optional
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

# Semantic Scholar API endpoints
SEMANTIC_SCHOLAR_API_BASE = "https://api.semanticscholar.org/graph/v1"
SEMANTIC_SCHOLAR_PAPER = f"{SEMANTIC_SCHOLAR_API_BASE}/paper"


class SemanticScholarClient:
    """
    Client for Semantic Scholar API.
    """

    def __init__(self, rate_limit_delay: float = 0.5, timeout: int = 10):
        """
        Initialize Semantic Scholar client.

        Args:
            rate_limit_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.session = requests.Session()
        self.last_request_time = 0.0

    def _rate_limit(self):
        """Apply rate limiting to API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _get_paper(self, query: str, fields: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Fetch paper metadata from Semantic Scholar.

        Args:
            query: arXiv ID, DOI, or search query
            fields: Specific fields to retrieve

        Returns:
            Paper metadata dictionary or None if not found
        """
        if fields is None:
            fields = [
                "paperId",
                "title",
                "authors",
                "year",
                "venue",
                "externalIds",
                "abstract",
            ]

        self._rate_limit()

        try:
            url = f"{SEMANTIC_SCHOLAR_PAPER}/{quote(query)}"
            params = {"fields": ",".join(fields)}
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.debug(f"Paper not found: {query}")
                return None
            else:
                logger.warning(
                    f"API error ({response.status_code}): {response.text[:200]}"
                )
                return None

        except requests.RequestException as e:
            logger.warning(f"API request failed: {e}")
            return None

    def fetch_by_arxiv_id(self, arxiv_id: str) -> Optional[Dict]:
        """
        Fetch paper metadata by arXiv ID.

        Args:
            arxiv_id: arXiv identifier (e.g., '2301.01234')

        Returns:
            Paper metadata or None
        """
        logger.debug(f"Fetching metadata for arXiv:{arxiv_id}")
        return self._get_paper(f"arXiv:{arxiv_id}")

    def fetch_by_title_and_authors(
        self, title: str, authors: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """
        Fetch paper metadata by title and optionally authors.

        Args:
            title: Paper title
            authors: List of author names

        Returns:
            Paper metadata or None
        """
        query = title
        if authors:
            query += f" {' '.join(authors[:2])}"

        logger.debug(f"Searching for paper: {query[:80]}...")
        return self._get_paper(query)


class BibTeXEnricher:
    """
    Enriches BibTeX entries using Semantic Scholar metadata.
    """

    ARXIV_PATTERN = re.compile(r"\d{4}\.\d{4,5}")

    def __init__(self, ss_client: Optional[SemanticScholarClient] = None):
        """
        Initialize BibTeX enricher.

        Args:
            ss_client: Semantic Scholar client instance
        """
        self.ss_client = ss_client or SemanticScholarClient()

    def extract_arxiv_id(self, entry: Dict) -> Optional[str]:
        """
        Extract arXiv ID from BibTeX entry.

        Args:
            entry: BibTeX entry dictionary

        Returns:
            arXiv ID or None
        """
        # Check eprint field
        if "eprint" in entry:
            eprint = entry["eprint"]
            match = self.ARXIV_PATTERN.search(str(eprint))
            if match:
                return match.group(0)

        # Check URL field
        if "url" in entry:
            url = entry["url"]
            match = self.ARXIV_PATTERN.search(url)
            if match:
                return match.group(0)

        # Check note field
        if "note" in entry:
            note = entry["note"]
            if "arxiv" in note.lower():
                match = self.ARXIV_PATTERN.search(note)
                if match:
                    return match.group(0)

        return None

    def replace_arxiv_entry(self, entry: Dict, paper_data: Dict) -> bool:
        """
        Replace/enrich arXiv entry with published metadata.

        Args:
            entry: BibTeX entry to update
            paper_data: Semantic Scholar paper metadata

        Returns:
            True if entry was successfully enriched
        """
        try:
            # Update basic fields
            if "title" in paper_data and paper_data["title"]:
                entry["title"] = paper_data["title"]

            if "year" in paper_data and paper_data["year"]:
                entry["year"] = str(paper_data["year"])

            # Update venue information
            if "venue" in paper_data and paper_data["venue"]:
                venue = paper_data["venue"]
                entry["booktitle"] = venue
                # Remove or update entry type if transitioning from preprint
                if entry.get("ENTRYTYPE") == "misc":
                    entry["ENTRYTYPE"] = "inproceedings"

            # Add DOI if available
            external_ids = paper_data.get("externalIds", {})
            if "DOI" in external_ids:
                entry["doi"] = external_ids["DOI"]

            # Expand author list
            if "authors" in paper_data:
                self.expand_author_list(entry, paper_data["authors"])

            # Update entry metadata
            entry["_enriched_by_semantic_scholar"] = True
            logger.info(f"Successfully enriched entry: {entry.get('ID', 'unknown')}")
            return True

        except Exception as e:
            logger.warning(f"Error enriching entry: {e}")
            return False

    def expand_author_list(
        self, entry: Dict, semantic_scholar_authors: List[Dict]
    ) -> bool:
        """
        Expand truncated author list using Semantic Scholar data.

        Args:
            entry: BibTeX entry to update
            semantic_scholar_authors: List of author dicts from Semantic Scholar

        Returns:
            True if author list was expanded
        """
        try:
            if not semantic_scholar_authors:
                return False

            # Format author names
            authors = []
            for author in semantic_scholar_authors:
                if isinstance(author, dict):
                    name = author.get("name", "")
                else:
                    name = str(author)

                if name:
                    authors.append(name)

            if authors:
                # Join authors in BibTeX format: "Name1 and Name2 and ..."
                author_string = " and ".join(authors)
                entry["author"] = author_string
                logger.debug(
                    f"Expanded author list with {len(authors)} authors"
                )
                return True

            return False

        except Exception as e:
            logger.warning(f"Error expanding author list: {e}")
            return False

    def enrich_entry(
        self, entry: Dict, expand_authors: bool = True, skip_errors: bool = True
    ) -> bool:
        """
        Complete enrichment workflow for a single entry.

        Args:
            entry: BibTeX entry to enrich
            expand_authors: Whether to expand author lists
            skip_errors: If True, log errors but continue; if False, raise

        Returns:
            True if enrichment was attempted/successful
        """
        try:
            # Skip if not a preprint
            if entry.get("ENTRYTYPE") != "misc":
                return False

            # Try to extract arXiv ID
            arxiv_id = self.extract_arxiv_id(entry)
            if not arxiv_id:
                return False

            # Fetch metadata from Semantic Scholar
            paper_data = self.ss_client.fetch_by_arxiv_id(arxiv_id)
            if not paper_data:
                logger.debug(f"No Semantic Scholar metadata found for {arxiv_id}")
                return False

            # Replace/enrich entry
            success = self.replace_arxiv_entry(entry, paper_data)
            return success

        except Exception as e:
            msg = f"Error enriching entry {entry.get('ID', 'unknown')}: {e}"
            if skip_errors:
                logger.warning(msg)
                return False
            else:
                raise ValueError(msg) from e
