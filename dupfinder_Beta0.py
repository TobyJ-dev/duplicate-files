"""
dupFinder.py - Recursive duplicate file finder with support for images, video, and music.
"""

import argparse
import csv
import hashlib
import shutil
import sys
from pathlib import Path

from tqdm import tqdm

from utils.logger import get_colored_logger

logger = get_colored_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHUNK_SIZE = 65536  # 64KB chunks for reading files during hashing

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
        '--output',
        type=Path,
        default=None,
        metavar='PATH',
        help='Save duplicate report to a CSV at this path. skipped_files.csv is saved alongside it.'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=False,
        help='Simulate the scan without moving or deleting any files.'
    )

    parser.add_argument(
        '--relocate',
        type=Path,
        default=None,
        metavar='PATH',
        help='Move duplicate files to this staging folder instead of deleting them.'
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
        help='Skip confirmation prompt when deleting. Must be used together with --delete.'
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

def scan_directory(directory: Path, extensions: set) -> tuple[list[Path], list[Path]]:
    matched = []
    skipped = []

    logger.info(f"Scanning: {directory}")

    all_files = [p for p in directory.rglob('*') if p.is_file()]
    logger.info(f"Total files found: {len(all_files)}")

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
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicates(file_list: list[Path]) -> dict[str, list[Path]]:
    hash_map: dict[str, list[Path]] = {}

    for filepath in tqdm(file_list, desc="Hashing files", unit="file"):
        file_hash = hash_file(filepath)
        if file_hash is None:
            continue
        if file_hash not in hash_map:
            hash_map[file_hash] = []
        hash_map[file_hash].append(filepath)

    duplicates = {h: paths for h, paths in hash_map.items() if len(paths) > 1}

    total_duplicate_files = sum(len(paths) for paths in duplicates.values())
    logger.info(f"Duplicate groups found: {len(duplicates)}")
    logger.info(f"Total files with duplicates: {total_duplicate_files}")

    return duplicates


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def save_report(
    duplicates: dict[str, list[Path]],
    skipped_files: list[Path],
    output_path: Path
) -> None:
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['group_hash', 'filepath', 'filename', 'extension', 'size_bytes'])
            for file_hash, paths in duplicates.items():
                for filepath in paths:
                    try:
                        size = filepath.stat().st_size
                    except OSError:
                        size = -1
                    writer.writerow([
                        file_hash,
                        str(filepath),
                        filepath.name,
                        filepath.suffix.lower(),
                        size,
                    ])
        logger.info(f"Duplicate report saved to: {output_path}")
    except OSError as e:
        logger.error(f"Could not write duplicate report: {e}")
        return

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
            logger.info(f"Skipped files report saved to: {skipped_path}")
        except OSError as e:
            logger.error(f"Could not write skipped files report: {e}")


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


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------

def handle_duplicates(duplicates: dict[str, list[Path]], args: argparse.Namespace) -> None:
    if not duplicates:
        logger.info("No duplicates to handle.")
        return

    total_to_act_on = sum(len(paths) - 1 for paths in duplicates.values())

    if args.dry_run:
        logger.info(f"Dry run: would act on {total_to_act_on} file(s) across {len(duplicates)} group(s).")
        for file_hash, paths in duplicates.items():
            sorted_paths = sorted(paths)
            logger.info(f"  Keep:   {sorted_paths[0]}")
            for filepath in sorted_paths[1:]:
                logger.info(f"  Remove: {filepath}")
        return

    if args.delete:
        if not args.yes:
            from cli.prompts import prompt_confirm_action
            if not prompt_confirm_action("permanently delete", total_to_act_on):
                logger.info("Deletion cancelled.")
                return
        _delete_duplicates(duplicates)

    elif args.relocate:
        if not args.yes:
            from cli.prompts import prompt_confirm_action
            if not prompt_confirm_action(f"move to {args.relocate}", total_to_act_on):
                logger.info("Relocation cancelled.")
                return
        _relocate_duplicates(duplicates, args.relocate)

    else:
        from cli.prompts import prompt_action, prompt_relocate_path, prompt_confirm_action
        action = prompt_action()
        if action == 'delete':
            if not prompt_confirm_action("permanently delete", total_to_act_on):
                logger.info("Deletion cancelled.")
                return
            _delete_duplicates(duplicates)
        elif action == 'relocate':
            relocate_path = prompt_relocate_path()
            if not prompt_confirm_action(f"move to {relocate_path}", total_to_act_on):
                logger.info("Relocation cancelled.")
                return
            _relocate_duplicates(duplicates, relocate_path)
        else:
            logger.info("No action taken.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    if args.verbose:
        logger.setLevel('DEBUG')

    if not args.directory.exists():
        logger.error(f"Directory does not exist: {args.directory}")
        sys.exit(1)

    if not args.directory.is_dir():
        logger.error(f"Path is not a directory: {args.directory}")
        sys.exit(1)

    active_extensions: set = set()
    if args.type:
        active_extensions.update(TYPE_MAP[args.type])
    for ext in args.ext:
        active_extensions.add(ext if ext.startswith('.') else f'.{ext}')

    logger.debug(f"Active extensions: {active_extensions if active_extensions else 'all files'}")

    file_list, skipped_files = scan_directory(args.directory, active_extensions)

    if not file_list:
        logger.info("No files found to scan. Exiting.")
        sys.exit(0)

    duplicates = find_duplicates(file_list)

    if not duplicates:
        logger.info("No duplicate files found. Exiting.")
        sys.exit(0)

    if args.output:
        save_report(duplicates, skipped_files, args.output)
    else:
        from cli.prompts import prompt_save_csv, prompt_csv_path
        if prompt_save_csv():
            csv_path = Path(prompt_csv_path())
            save_report(duplicates, skipped_files, csv_path)

    handle_duplicates(duplicates, args)


if __name__ == "__main__":
    main()