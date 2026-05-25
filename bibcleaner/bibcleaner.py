"""
Main BibCleaner class that orchestrates the bibliography enrichment pipeline.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import bibtexparser
from bibtexparser.model import Entry
from tqdm import tqdm

from .enricher import BibTeXEnricher, SemanticScholarClient

logger = logging.getLogger(__name__)


class BibCleaner:
    """
    Main BibCleaner orchestration class.

    Workflow:
    1. Read BibTeX file
    2. Parse entries
    3. Enrich arXiv entries with published metadata
    4. Expand author lists
    5. Write enriched bibliography
    """

    def __init__(
        self,
        rate_limit_delay: float = 0.5,
        log_level: str = "INFO",
    ):
        """
        Initialize BibCleaner.

        Args:
            rate_limit_delay: Delay between API requests (seconds)
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.rate_limit_delay = rate_limit_delay
        self.log_level = log_level

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Initialize components
        self.ss_client = SemanticScholarClient(
            rate_limit_delay=rate_limit_delay
        )
        self.enricher = BibTeXEnricher(ss_client=self.ss_client)

    def read_bib_file(self, filepath: str) -> bibtexparser.Library:
        """
        Read and parse BibTeX file.

        Args:
            filepath: Path to .bib file

        Returns:
            Parsed BibTeX library

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If parsing fails
        """
        path = Path(filepath)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                bibtex_str = f.read()
                library = bibtexparser.parse_string(bibtex_str)
                logger.info(f"Parsed {len(library.entries)} entries from {filepath}")
                return library
        except Exception as e:
            raise ValueError(f"Error parsing BibTeX file: {e}") from e

    def write_bib_file(self, library: bibtexparser.Library, filepath: str) -> None:
        """
        Write enriched bibliography to file.

        Args:
            library: BibTeX library to write
            filepath: Output file path
        """
        try:
            output_str = bibtexparser.write_string(library)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(output_str)
            logger.info(f"Wrote enriched bibliography to {filepath}")
        except Exception as e:
            raise ValueError(f"Error writing BibTeX file: {e}") from e

    def enrich_bibliography(
        self,
        library: bibtexparser.Library,
        expand_authors: bool = True,
        skip_errors: bool = True,
    ) -> bibtexparser.Library:
        """
        Enrich all entries in bibliography.

        Args:
            library: BibTeX library to enrich
            expand_authors: Whether to expand author lists
            skip_errors: If True, skip problematic entries; if False, stop on error

        Returns:
            Enriched library
        """
        enriched_count = 0
        skipped_count = 0
        error_count = 0

        logger.info(f"Starting enrichment of {len(library.entries)} entries...")

        for entry in tqdm(library.entries, desc="Enriching bibliography"):
            try:
                # Convert Entry object to dict for easier handling
                entry_dict = entry.dict()

                # Attempt enrichment
                success = self.enricher.enrich_entry(
                    entry_dict,
                    expand_authors=expand_authors,
                    skip_errors=skip_errors,
                )

                if success:
                    enriched_count += 1
                else:
                    skipped_count += 1

                # Update entry with enriched data
                for key, value in entry_dict.items():
                    if key != "ID" and key != "ENTRYTYPE":
                        setattr(entry, key, value)

            except Exception as e:
                error_count += 1
                logger.error(f"Error processing entry {entry.key}: {e}")
                if not skip_errors:
                    raise

        logger.info(
            f"Enrichment complete: {enriched_count} enriched, "
            f"{skipped_count} skipped, {error_count} errors"
        )

        return library

    def process(
        self,
        input_file: str,
        output_file: str,
        expand_authors: bool = True,
        skip_errors: bool = True,
    ) -> None:
        """
        Complete pipeline: read → enrich → write.

        Args:
            input_file: Path to input .bib file
            output_file: Path to output .bib file
            expand_authors: Whether to expand author lists
            skip_errors: If True, skip problematic entries
        """
        logger.info("Starting BibCleaner pipeline...")
        logger.info(f"Input file:  {input_file}")
        logger.info(f"Output file: {output_file}")

        try:
            # Read
            library = self.read_bib_file(input_file)

            # Enrich
            library = self.enrich_bibliography(
                library,
                expand_authors=expand_authors,
                skip_errors=skip_errors,
            )

            # Write
            self.write_bib_file(library, output_file)

            logger.info("Pipeline completed successfully!")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
