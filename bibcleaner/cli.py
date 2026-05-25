"""
Command-line interface for BibCleaner.
"""

import argparse
import logging
import sys

from .bibcleaner import BibCleaner

logger = logging.getLogger(__name__)


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="BibCleaner: Automated BibTeX metadata enrichment toolkit.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  bibcleaner input.bib output.bib
  bibcleaner input.bib output.bib --no-expand-authors
  bibcleaner input.bib output.bib --log-level DEBUG
        """,
    )

    parser.add_argument(
        "input",
        type=str,
        help="Path to input BibTeX file",
    )

    parser.add_argument(
        "output",
        type=str,
        help="Path to output BibTeX file",
    )

    parser.add_argument(
        "--expand-authors",
        action="store_true",
        default=True,
        help="Expand truncated author lists (default: True)",
    )

    parser.add_argument(
        "--no-expand-authors",
        action="store_false",
        dest="expand_authors",
        help="Do not expand author lists",
    )

    parser.add_argument(
        "--skip-errors",
        action="store_true",
        default=True,
        help="Skip entries that fail enrichment (default: True)",
    )

    parser.add_argument(
        "--stop-on-error",
        action="store_false",
        dest="skip_errors",
        help="Stop on first error",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    parser.add_argument(
        "--rate-limit-delay",
        type=float,
        default=0.5,
        help="Delay between API requests in seconds (default: 0.5)",
    )

    args = parser.parse_args()

    # Initialize BibCleaner
    try:
        cleaner = BibCleaner(
            rate_limit_delay=args.rate_limit_delay,
            log_level=args.log_level,
        )

        # Process bibliography
        cleaner.process(
            input_file=args.input,
            output_file=args.output,
            expand_authors=args.expand_authors,
            skip_errors=args.skip_errors,
        )

        print(f"✓ Successfully processed bibliography!")
        print(f"  Input:  {args.input}")
        print(f"  Output: {args.output}")

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error processing bibliography: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
