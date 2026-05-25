"""
BibCleaner: Automated BibTeX metadata enrichment toolkit.

A Python toolkit for cleaning and enriching BibTeX bibliographies by:
- Replacing arXiv preprints with published venue metadata
- Expanding truncated author lists using Semantic Scholar API
- Validating and standardizing citation formatting
"""

__version__ = "0.1.0"
__author__ = "Hamada Zahera"
__license__ = "MIT"

from .bibcleaner import BibCleaner
from .enricher import BibTeXEnricher, SemanticScholarClient

__all__ = ["BibCleaner", "BibTeXEnricher", "SemanticScholarClient"]
