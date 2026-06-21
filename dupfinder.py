"""
dupFinder.py - Recursive duplicate file finder with support for images, video, and music.
"""

import argparse
import csv
import hashlib
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

from tqdm import tqdm

from utils.logger import get_colored_logger
from cli.logo import print_logo
from cli.prompts import (
    prompt_save_csv,
    prompt_csv_path,
    prompt_confirm_action,
    prompt_action,
    prompt_relocate_path,
    prompt_dry_run_first,
    prompt_proceed_with_action,
)

logger = get_colored_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNK_SIZE = 65536  # 64KB chunks for reading files during hashing

SCRIPT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_PATH = SCRIPT_ROOT / "output" / "duplicates_report.csv"
DEFAULT_LOGS_DIR = SCRIPT_ROOT / "logs"
DEFAULT_STAGING_FOLDER_NAME = "duplicates"
# RELOCATE_DEFAULT_SENTINEL = "__USE_DEFAULT__"
# RELOCATE_DEFAULT_SENTINEL = None
RELOCATE_DEFAULT_SENTINEL = object()  # unique sentinel value that cannot be confused with a real path

PLAIN_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
PLAIN_LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'

IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.heic', '.heif',
    '.raw', '.cr2', '.cr3', '.dng', '.tiff',
    '.tif', '.bmp', '.gif', '.webp', '.nef'
}

VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.wmv',
    '.flv', '.m4v', '.mpeg', '.mpg', '.3gp',
    '.ts', '.mts', '.m2ts', '.webm', '.vob'
}

MUSIC_EXTENSIONS = {
    '.mp3', '.flac', '.wav', '.aac', '.m4a',
    '.ogg', '.wma', '.aiff', '.alac', '.opus',
    '.m4b', '.mp2'
}

TYPE_MAP = {
    'images': IMAGE_EXTENSIONS,
    'video':  VIDEO_EXTENSIONS,
    'music':  MUSIC_EXTENSIONS,
}


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Recursively find and optionally remove duplicate files.',
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument(
        'directory',
        type=Path,
        help='Root directory to scan for duplicates.'
    )

    parser.add_argument(
        '--type',
        choices=['images', 'video', 'music'],
        default=None,
        help='Filter by file type. If omitted, all files are scanned.'
    )

    parser.add_argument(
        '--ext',
        nargs='+',
        default=[],
        metavar='EXTENSION',
        help='Additional extensions to include (e.g. --ext .raw .dng). Adds to --type if given.'
    )

    parser.add_argument(
            '--exclude',
            nargs='+',
            default=[],
            metavar='KEYWORD',
            help='Exclude any folder whose name contains one of these keywords (case-insensitive).\n'
                'Substring match: --exclude selection also catches selection2026.\n'
                'e.g. --exclude selection backup tmp'
        )

    parser.add_argument(
        '--output',
        type=Path,
        default=None,
        metavar='PATH',
        help='Save duplicate report to a CSV at this path. skipped_files.csv is saved alongside it.\n'
             'If omitted, the default path is used whenever a report is saved.'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Simulate the scan without moving or deleting any files.'
    )
    
    parser.add_argument(
            '--relocate',
            nargs='?',
            const=RELOCATE_DEFAULT_SENTINEL,
            default=None,
            metavar='PATH',
            help='Move duplicate files to a staging folder instead of deleting them.\n'
                'If used without a value, defaults to <directory>/duplicates.'
        )
    
    parser.add_argument(
        '--load-report',
        type=Path,
        default=None,
        metavar='PATH',
        help='Load an existing duplicate report CSV instead of scanning.\n'
             'Must be combined with --delete or --relocate.\n'
             'Only rows with status=delete are acted on.\n'
             'You can manually remove rows from the CSV before loading it.'
    )

    parser.add_argument(
        '--delete',
        action='store_true',
        default=False,
        help='Permanently delete duplicate files.'
    )

    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        default=False,
        help='Skip confirmation prompt when deleting or relocating.\n'
             'Has no effect without --delete or --relocate.'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        default=False,
        help='Enable debug-level logging.'
    )

    return parser.parse_args()


# ---------------------------------------------------------------------------
# File hashing
# ---------------------------------------------------------------------------

def hash_file(filepath: Path) -> str | None:
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(CHUNK_SIZE):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (OSError, PermissionError) as e:
        logger.warning(f"Could not read file, skipping: {filepath} - {e}")
        return None


# ---------------------------------------------------------------------------
# Directory scanning
# ---------------------------------------------------------------------------

def scan_directory(
    directory: Path,
    extensions: set,
    exclude_keywords: list[str]
) -> tuple[list[Path], list[Path]]:
    matched = []
    skipped = []
    excluded_count = 0
    staging_default = directory / DEFAULT_STAGING_FOLDER_NAME

    logger.info(f"Scanning: {directory}")
    if exclude_keywords:
        logger.info(f"Excluding folders containing: {exclude_keywords}")

    all_files = []
    for p in directory.rglob('*'):
        if not p.is_file():
            continue
        if staging_default in p.parents:
            continue
        if _is_excluded(p, exclude_keywords):
            excluded_count += 1
            continue
        all_files.append(p)

    logger.info(f"Total files found: {len(all_files)}")
    if excluded_count > 0:
        logger.info(f"Files excluded by folder filter: {excluded_count}")

    if not extensions:
        matched = all_files
    else:
        for filepath in all_files:
            if filepath.suffix.lower() in extensions:
                matched.append(filepath)
            else:
                skipped.append(filepath)

    logger.info(f"Files to hash: {len(matched)}")
    if skipped:
        logger.info(f"Files skipped by extension filter: {len(skipped)}")

    return matched, skipped


# ---------------------------------------------------------------------------
# exclude folders with specified keywords/name patterns in their path
# ---------------------------------------------------------------------------
def _is_excluded(filepath: Path, exclude_keywords: list[str]) -> bool:
    """
    Return True if any directory component of the path contains one of the
    exclude keywords as a case-insensitive substring.
    Only checks folder names, not the filename itself.

    Example: keyword 'selection' matches both
        .../selection/file.jpg  and  .../selection2026/file.jpg
    """
    if not exclude_keywords:
        return False
    for part in filepath.parent.parts:
        for keyword in exclude_keywords:
            if keyword.lower() in part.lower():
                return True
    return False


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicates(file_list: list[Path]) -> dict[str, list[Path]]:
    hash_map: dict[str, list[Path]] = {}

    logger.info(f"Starting hashing {len(file_list)} file(s). This may take several minutes...")

    for filepath in tqdm(file_list, desc="Hashing files", unit="file"):
        file_hash = hash_file(filepath)
        if file_hash is None:
            continue
        if file_hash not in hash_map:
            hash_map[file_hash] = []
        hash_map[file_hash].append(filepath)

    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}

    total_duplicate_files = sum(len(paths) for paths in duplicates.values())
    logger.info("-" * 70)
    logger.info(f"Hashing complete.")
    logger.info(f"Duplicate groups found: {len(duplicates)}")
    logger.info(f"Total files with duplicates: {total_duplicate_files}")
    logger.info("-" * 70)

    return duplicates


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def save_report(
    duplicates: dict[str, list[Path]],
    skipped_files: list[Path],
    output_path: Path
) -> float:                          # now returns total_mb_freed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_bytes_freed = 0

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'filename', 'size_bytes', 'size_mb',
                'path', 'extension', 'group_hash', 'status'
            ])

            for file_hash, paths in duplicates.items():
                sorted_paths = sorted(paths)
                for i, filepath in enumerate(sorted_paths):
                    status = 'keep' if i == 0 else 'delete'
                    try:
                        size_bytes = filepath.stat().st_size
                    except OSError:
                        size_bytes = -1

                    size_mb = round(size_bytes / (1024 * 1024), 4) if size_bytes >= 0 else -1

                    if status == 'delete' and size_bytes >= 0:
                        total_bytes_freed += size_bytes

                    writer.writerow([
                        filepath.name,
                        size_bytes,
                        size_mb,
                        str(filepath),
                        filepath.suffix.lower(),
                        file_hash,
                        status,
                    ])

            total_mb_freed = round(total_bytes_freed / (1024 * 1024), 2)
            writer.writerow([])
            writer.writerow([
                f'You would free {total_mb_freed} MB by deleting these duplicates',
                '', '', '', '', '', ''
            ])

    except OSError as e:
        logger.error(f"Could not write duplicate report: {e}")
        return 0.0

    if skipped_files:
        skipped_path = output_path.parent / 'skipped_files.csv'
        try:
            with open(skipped_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['filepath', 'filename', 'extension'])
                for filepath in skipped_files:
                    writer.writerow([
                        str(filepath),
                        filepath.name,
                        filepath.suffix.lower(),
                    ])
        except OSError as e:
            logger.error(f"Could not write skipped files report: {e}")

    return total_mb_freed

# ---------------------------------------------------------------------------
# Use existing report if flag is specified
# avoids re-scan and re-hash
# ---------------------------------------------------------------------------

def load_report(report_path: Path) -> list[Path]:
    """
    Read a previously saved duplicates CSV and return only the file paths
    marked with status 'delete'.

    Rows with missing or non-matching status are silently skipped, including
    the summary row at the end of the file. The user can manually remove rows
    from the CSV before loading it here to exclude specific files from the action.
    """
    if not report_path.exists():
        logger.error(f"Report file not found: {report_path}")
        sys.exit(1)

    file_list = []
    try:
        with open(report_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            if 'status' not in fields or 'path' not in fields:
                logger.error(
                    "Report is missing required columns 'path' and/or 'status'. "
                    "Make sure the file was generated by dupFinder."
                )
                sys.exit(1)
            for row in reader:
                if row.get('status', '').strip() == 'delete':
                    raw_path = row.get('path', '').strip()
                    if raw_path:
                        file_list.append(Path(raw_path))
    except OSError as e:
        logger.error(f"Could not read report: {e}")
        sys.exit(1)

    logger.info(f"Loaded {len(file_list)} file(s) marked for deletion from: {report_path}")
    return file_list


# ---------------------------------------------------------------------------
# File operations (private helpers)
# ---------------------------------------------------------------------------

def _delete_duplicates(duplicates: dict[str, list[Path]]) -> None:
    deleted_count = 0
    for file_hash, paths in duplicates.items():
        sorted_paths = sorted(paths)
        logger.debug(f"Keeping: {sorted_paths[0]}")
        for filepath in sorted_paths[1:]:
            try:
                filepath.unlink()
                logger.info(f"Deleted: {filepath}")
                deleted_count += 1
            except OSError as e:
                logger.error(f"Could not delete {filepath}: {e}")
    logger.info(f"Deletion complete. {deleted_count} file(s) deleted.")


def _delete_file_list(file_list: list[Path]) -> None:
    """
    Delete a flat list of file paths.
    Used when acting on an existing report rather than a fresh scan.
    Files that no longer exist on disk are skipped with a warning.
    """
    deleted_count = 0
    for filepath in file_list:
        if not filepath.exists():
            logger.warning(f"File no longer exists, skipping: {filepath}")
            continue
        try:
            filepath.unlink()
            logger.info(f"Deleted: {filepath}")
            deleted_count += 1
        except OSError as e:
            logger.error(f"Could not delete {filepath}: {e}")
    logger.info(f"Deletion complete. {deleted_count} file(s) deleted.")


def _relocate_duplicates(duplicates: dict[str, list[Path]], relocate_path: Path) -> None:
    relocate_path.mkdir(parents=True, exist_ok=True)
    moved_count = 0
    for file_hash, paths in duplicates.items():
        sorted_paths = sorted(paths)
        logger.debug(f"Keeping: {sorted_paths[0]}")
        for filepath in sorted_paths[1:]:
            destination = relocate_path / filepath.name
            if destination.exists():
                destination = relocate_path / f"{filepath.stem}_{file_hash[:8]}{filepath.suffix}"
            try:
                shutil.move(str(filepath), str(destination))
                logger.info(f"Moved: {filepath} -> {destination}")
                moved_count += 1
            except OSError as e:
                logger.error(f"Could not move {filepath}: {e}")
    logger.info(f"Relocation complete. {moved_count} file(s) moved to {relocate_path}.")


def _relocate_file_list(file_list: list[Path], relocate_path: Path) -> None:
    """
    Move a flat list of file paths to a staging folder.
    Used when acting on an existing report rather than a fresh scan.
    Files that no longer exist on disk are skipped with a warning.
    Naming collisions in the destination are resolved with a numeric suffix.
    """
    relocate_path.mkdir(parents=True, exist_ok=True)
    moved_count = 0
    for filepath in file_list:
        if not filepath.exists():
            logger.warning(f"File no longer exists, skipping: {filepath}")
            continue
        destination = relocate_path / filepath.name
        if destination.exists():
            counter = 1
            while destination.exists():
                destination = relocate_path / f"{filepath.stem}_{counter}{filepath.suffix}"
                counter += 1
        try:
            shutil.move(str(filepath), str(destination))
            logger.info(f"Moved: {filepath} -> {destination}")
            moved_count += 1
        except OSError as e:
            logger.error(f"Could not move {filepath}: {e}")
    logger.info(f"Relocation complete. {moved_count} file(s) moved to {relocate_path}.")


def resolve_relocate_path(args: argparse.Namespace) -> Path:
    if args.relocate is RELOCATE_DEFAULT_SENTINEL:
        return args.directory / DEFAULT_STAGING_FOLDER_NAME
    return Path(args.relocate)

# ---------------------------------------------------------------------------
# Logging setup helpers
# ---------------------------------------------------------------------------

def setup_normal_log_handler(log_path: Path, debug: bool) -> logging.FileHandler:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_path, encoding='utf-8')
    handler.setLevel(logging.DEBUG if debug else logging.INFO)
    handler.setFormatter(logging.Formatter(fmt=PLAIN_LOG_FORMAT, datefmt=PLAIN_LOG_DATEFMT))
    logging.getLogger().addHandler(handler)
    return handler


class _ActionLogFilter(logging.Filter):
    """Lets through only log records whose message starts with the given prefix."""

    def __init__(self, prefix: str):
        super().__init__()
        self.prefix = prefix

    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().startswith(self.prefix)


def setup_action_log_handler(log_path: Path, prefix: str) -> logging.FileHandler:
    handler = logging.FileHandler(log_path, encoding='utf-8')
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(fmt=PLAIN_LOG_FORMAT, datefmt=PLAIN_LOG_DATEFMT))
    handler.addFilter(_ActionLogFilter(prefix))
    logging.getLogger().addHandler(handler)
    return handler


def teardown_log_handler(handler: logging.FileHandler) -> None:
    handler.close()
    logging.getLogger().removeHandler(handler)


# ---------------------------------------------------------------------------
# Interactive / dry-run flow
# ---------------------------------------------------------------------------

def show_dry_run_preview(duplicates: dict[str, list[Path]]) -> None:
    total_to_remove = sum(len(paths) - 1 for paths in duplicates.values())
    logger.info("-" * 70)
    logger.info(f"DRY RUN PREVIEW: {len(duplicates)} group(s), {total_to_remove} file(s) would be removed.")
    logger.info("-" * 70)
    for file_hash, paths in duplicates.items():
        sorted_paths = sorted(paths)
        logger.info(f"  Keep:   {sorted_paths[0]}")
        for filepath in sorted_paths[1:]:
            logger.info(f"  Remove: {filepath}")
    logger.info("-" * 70)


def prompt_and_save_csv(duplicates: dict[str, list[Path]], skipped_files: list[Path]) -> None:
    if prompt_save_csv():
        csv_path = prompt_csv_path(DEFAULT_OUTPUT_PATH)
        save_report(duplicates, skipped_files, csv_path)


def run_action_menu(duplicates: dict[str, list[Path]], args: argparse.Namespace, timestamp: str) -> None:
    total_to_act_on = sum(len(paths) - 1 for paths in duplicates.values())
    action = prompt_action()

    if action == 'delete':
        if not prompt_confirm_action("permanently delete", total_to_act_on):
            logger.info("Deletion cancelled.")
            return
        handler = setup_action_log_handler(DEFAULT_LOGS_DIR / f"delete_{timestamp}.log", "Deleted:")
        _delete_duplicates(duplicates)
        teardown_log_handler(handler)

    elif action == 'relocate':
        relocate_path = prompt_relocate_path(args.directory / DEFAULT_STAGING_FOLDER_NAME)
        if not prompt_confirm_action(f"move to {relocate_path}", total_to_act_on):
            logger.info("Relocation cancelled.")
            return
        handler = setup_action_log_handler(DEFAULT_LOGS_DIR / f"relocate_{timestamp}.log", "Moved:")
        _relocate_duplicates(duplicates, relocate_path)
        teardown_log_handler(handler)

    else:
        logger.info("No action taken.")


def run_interactive_flow(
    duplicates: dict[str, list[Path]],
    skipped_files: list[Path],
    args: argparse.Namespace,
    timestamp: str
) -> None:
    if prompt_dry_run_first():
        show_dry_run_preview(duplicates)
        if not prompt_proceed_with_action():
            prompt_and_save_csv(duplicates, skipped_files)
            logger.info("Exiting without taking action.")
            return

    prompt_and_save_csv(duplicates, skipped_files)
    run_action_menu(duplicates, args, timestamp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print_logo()
    args = parse_args()

    if args.yes and not (args.delete or args.relocate is not None):
        logger.warning("--yes has no effect without --delete or --relocate.")

    if args.load_report is not None and not (args.delete or args.relocate is not None):
        logger.error("--load-report requires --delete or --relocate.")
        sys.exit(1)

    if not args.directory.exists():
        logger.error(f"Directory does not exist: {args.directory}")
        sys.exit(1)

    if not args.directory.is_dir():
        logger.error(f"Path is not a directory: {args.directory}")
        sys.exit(1)

    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    setup_normal_log_handler(DEFAULT_LOGS_DIR / f"dupfinder_{timestamp}.log", debug=args.verbose)

    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('cli.prompts').setLevel(logging.DEBUG)

    active_extensions: set = set()
    if args.type:
        active_extensions.update(TYPE_MAP[args.type])
    for ext in args.ext:
        active_extensions.add(ext if ext.startswith('.') else f'.{ext}')

    logger.debug(f"Active extensions: {active_extensions if active_extensions else 'all files'}")
    if args.exclude:
        logger.debug(f"Exclude keywords: {args.exclude}")

    # --load-report: skip scanning entirely, act directly on the report
    if args.load_report is not None:
        file_list = load_report(args.load_report)
        if not file_list:
            logger.info("No files marked for deletion found in report. Exiting.")
            sys.exit(0)
        total_to_act_on = len(file_list)
        logger.info("=" * 70)
        logger.info(f"Acting on {total_to_act_on} file(s) from: {args.load_report}")
        logger.info("=" * 70)

        if args.delete:
            if not args.yes:
                if not prompt_confirm_action("permanently delete", total_to_act_on):
                    logger.info("Deletion cancelled.")
                    return
            handler = setup_action_log_handler(
                DEFAULT_LOGS_DIR / f"delete_{timestamp}.log", "Deleted:"
            )
            _delete_file_list(file_list)
            teardown_log_handler(handler)
        else:
            relocate_path = resolve_relocate_path(args)
            if not args.yes:
                if not prompt_confirm_action(f"move to {relocate_path}", total_to_act_on):
                    logger.info("Relocation cancelled.")
                    return
            handler = setup_action_log_handler(
                DEFAULT_LOGS_DIR / f"relocate_{timestamp}.log", "Moved:"
            )
            _relocate_file_list(file_list, relocate_path)
            teardown_log_handler(handler)
        return

    # scan phase
    logger.info("=" * 70)
    file_list, skipped_files = scan_directory(args.directory, active_extensions, args.exclude)
    logger.info("=" * 70)

    if not file_list:
        logger.info("No files found to scan. Exiting.")
        sys.exit(0)

    duplicates = find_duplicates(file_list)
    logger.info("=" * 70)

    if not duplicates:
        logger.info("No duplicate files found. Exiting.")
        sys.exit(0)

    # --dry-run: preview only, no action taken
    if args.dry_run:
        show_dry_run_preview(duplicates)
        if args.output:
            mb_freed = save_report(duplicates, skipped_files, args.output)
            logger.info("=" * 70)
            logger.info(f"Report saved to:            {args.output}")
            logger.info(f"Skipped files saved to:     {args.output.parent / 'skipped_files.csv'}")
            logger.info(f"Potential space to free:    {mb_freed} MB")
            logger.info("=" * 70)
        return

    # --delete or --relocate: scan done, save report and act
    if args.delete or args.relocate is not None:
        output_path = args.output if args.output else DEFAULT_OUTPUT_PATH
        mb_freed = save_report(duplicates, skipped_files, output_path)
        logger.info("=" * 70)
        logger.info(f"Report saved to:            {output_path}")
        logger.info(f"Skipped files saved to:     {output_path.parent / 'skipped_files.csv'}")
        logger.info(f"Potential space to free:    {mb_freed} MB")
        logger.info("=" * 70)
        total_to_act_on = sum(len(paths) - 1 for paths in duplicates.values())

        if args.delete:
            if not args.yes:
                if not prompt_confirm_action("permanently delete", total_to_act_on):
                    logger.info("Deletion cancelled.")
                    return
            handler = setup_action_log_handler(
                DEFAULT_LOGS_DIR / f"delete_{timestamp}.log", "Deleted:"
            )
            _delete_duplicates(duplicates)
            teardown_log_handler(handler)
        else:
            relocate_path = resolve_relocate_path(args)
            if not args.yes:
                if not prompt_confirm_action(f"move to {relocate_path}", total_to_act_on):
                    logger.info("Relocation cancelled.")
                    return
            handler = setup_action_log_handler(
                DEFAULT_LOGS_DIR / f"relocate_{timestamp}.log", "Moved:"
            )
            _relocate_duplicates(duplicates, relocate_path)
            teardown_log_handler(handler)
        return

    # --output only: save and exit, no action menu
    if args.output:
        mb_freed = save_report(duplicates, skipped_files, args.output)
        logger.info("=" * 70)
        logger.info(f"Report saved to:            {args.output}")
        logger.info(f"Skipped files saved to:     {args.output.parent / 'skipped_files.csv'}")
        logger.info(f"Potential space to free:    {mb_freed} MB")
        logger.info("=" * 70)
        return

    # no relevant flags: full interactive flow
    run_interactive_flow(duplicates, skipped_files, args, timestamp)


if __name__ == "__main__":
    main()