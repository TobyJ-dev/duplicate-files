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


def prompt_dry_run_first() -> bool:
    """Ask the user if they want to preview changes with a dry run before acting."""
    return prompt_yes_no("Would you like to perform a dry run first to preview the changes?")


def prompt_proceed_with_action() -> bool:
    """Ask the user, after seeing a dry run preview, if they want to proceed with an action."""
    return prompt_yes_no("Would you like to proceed with an action now?")


def prompt_save_csv() -> bool:
    """Ask the user if they want to save the results to a CSV file."""
    return prompt_yes_no("Do you want to save the results to a CSV file?")


def prompt_csv_path(default_path: Path) -> Path:
    """
    Ask the user for a CSV output file path.
    Empty input uses default_path. A path not ending in .csv gets the
    extension appended automatically.
    """
    try:
        raw = input(f"Enter output path (leave empty for default: {default_path}): ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        logger.info("Input interrupted. Exiting.")
        sys.exit(0)

    if raw == "":
        logger.info(f"No path entered. Using default: {default_path}")
        return default_path

    path = Path(raw)
    if path.suffix.lower() != '.csv':
        path = path.with_suffix('.csv')
        logger.warning(f"Output path did not end in .csv. Using: {path}")
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


def prompt_relocate_path(default_path: Path) -> Path:
    """Ask the user for a staging folder path. Empty input uses default_path."""
    try:
        raw = input(f"Enter staging folder path (leave empty for default: {default_path}): ").strip()
    except (KeyboardInterrupt, EOFError):
        print()
        logger.info("Input interrupted. Exiting.")
        sys.exit(0)

    if raw == "":
        logger.info(f"No path entered. Using default: {default_path}")
        return default_path

    return Path(raw)