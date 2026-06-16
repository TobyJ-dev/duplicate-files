"""
cli/prompts.py - User interaction prompts for dupFinder.
"""

import sys
from pathlib import Path

from utils.logger import get_colored_logger

logger = get_colored_logger(__name__)


def prompt_yes_no(question: str) -> bool:
    """Ask a yes/no question. Returns True for yes, False for no."""
    while True:
        try:
            answer = input(f"{question} (y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            logger.info("Input interrupted. Exiting.")
            sys.exit(0)
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        print("Please enter y or n.")


def prompt_save_csv() -> bool:
    """Ask the user if they want to save the results to a CSV file."""
    return prompt_yes_no("Do you want to save the results to a CSV file?")


def prompt_csv_path() -> str:
    """Ask the user for a CSV output file path."""
    try:
        path = input("Enter output path (e.g. /output/report.csv): ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        logger.info("Input interrupted. Exiting.")
        sys.exit(0)
    return path


def prompt_confirm_action(action: str, count: int) -> bool:
    """Ask the user to confirm a destructive action on a number of files."""
    return prompt_yes_no(
        f"This will {action} {count} file(s). Are you sure? This cannot be undone."
    )


def prompt_action() -> str:
    """
    Ask what to do with found duplicates.
    Returns 'delete', 'relocate', or 'skip'.
    """
    print("\nWhat would you like to do with the duplicate files?")
    print("  [d] Delete them permanently")
    print("  [r] Move them to a staging folder")
    print("  [s] Skip, do nothing")
    while True:
        try:
            answer = input("Choice (d/r/s): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            logger.info("Input interrupted. Exiting.")
            sys.exit(0)
        if answer in ('d', 'delete'):
            return 'delete'
        if answer in ('r', 'relocate', 'move'):
            return 'relocate'
        if answer in ('s', 'skip'):
            return 'skip'
        print("Please enter d, r, or s.")


def prompt_relocate_path() -> Path:
    """Ask the user for a staging folder path."""
    try:
        path = input("Enter staging folder path: ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        logger.info("Input interrupted. Exiting.")
        sys.exit(0)
    return Path(path)
