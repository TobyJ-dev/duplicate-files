# duplicate-finder

A command-line tool to find and optionally remove duplicate files,
with support for images, video, and music files.

## Features

- Recursive directory scan
- Content-based duplicate detection via MD5 hashing
- Optional filtering by file type (images, video, music) or custom extensions
- CSV report export, including a separate report of files skipped by the extension filter
- Dry run mode to preview changes before acting
- Safe staging mode (move duplicates to a folder) or permanent deletion
- Full logging of every run, plus a dedicated log of every file deleted or moved
- Interactive prompts when run without flags, fully scriptable with flags

## Requirements

Python 3.10+

## Installation

```
git clone <your-repo-url>
cd duplicate-finder
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

### Basic scan, fully interactive

```
python dupFinder.py D:\Photos
```

No flags at all. This walks you through:
1. Whether to run a dry run first to preview what would happen
2. Whether to save a CSV report (default: `output/duplicates_report.csv`, relative to the project folder)
3. What to do with the duplicates: delete, move to a staging folder, or skip

### Filter by file type

```
python dupFinder.py D:\Photos --type images
python dupFinder.py D:\Music --type music
python dupFinder.py D:\Videos --type video
```

Filtering happens before hashing. Files outside the chosen type are never read, only their filenames are checked against the extension list. This matters on large drives, since hashing is the slow part.

### Add custom extensions on top of a type

```
python dupFinder.py D:\Photos --type images --ext .c2c .arw
```

### Scan everything, no type filter

```
python dupFinder.py D:\Backup
```

Omit `--type` and every file is hashed regardless of extension.

### Save a report without taking any other action

```
python dupFinder.py D:\Photos --output report.csv
```

Scans, saves `report.csv` plus `skipped_files.csv` in the same folder, and exits. No prompts.

### Preview only, no changes

```
python dupFinder.py D:\Photos --dry-run
```

Shows which file in each duplicate group would be kept and which would be removed, without touching anything.

### Delete duplicates

```
python dupFinder.py D:\Photos --delete
```

Saves a report at the default path, asks for confirmation, then deletes. Writes a dedicated delete log to the `logs` folder listing every file removed.

```
python dupFinder.py D:\Photos --delete --yes
```

Same, but skips the confirmation prompt. Use this only once you trust the result, for example after reviewing a `--dry-run` first.

### Move duplicates to a staging folder instead of deleting

```
python dupFinder.py D:\Photos --relocate
```

Moves duplicates into `D:\Photos\duplicates` (created automatically if missing).

```
python dupFinder.py D:\Photos --relocate D:\Staging\dupes
```

Moves duplicates into a custom folder instead.

Add `--yes` to either of the above to skip the confirmation prompt.

## Defaults

- CSV report: `output/duplicates_report.csv`, relative to the project folder, used whenever a report needs to be saved and no `--output` path was given.
- Skipped files report: always saved next to the duplicates report, named `skipped_files.csv`.
- Staging folder: `<scanned directory>/duplicates`, used when `--relocate` is passed without a path.
- Logs: always written to the `logs` folder at the project root, regardless of which directory you scan. Every run produces a normal log of everything printed to the console. Runs that delete or relocate files also produce a dedicated `delete_<timestamp>.log` or `relocate_<timestamp>.log` containing only the lines for files actually removed or moved.

The tool automatically skips its own default staging folder (`<scanned directory>/duplicates`) during a scan, so re-running it after a relocation does not treat already-relocated files as a new batch of duplicates.

## All flags

| Flag | Description |
|---|---|
| `directory` | Root directory to scan (required, positional) |
| `--type {images,video,music}` | Filter by file type |
| `--ext .ext1 .ext2 ...` | Add custom extensions, combinable with `--type` |
| `--output PATH` | Save the duplicates report to this CSV path |
| `--dry-run` | Preview only, no changes made |
| `--relocate [PATH]` | Move duplicates to a staging folder. Defaults to `<directory>/duplicates` if no path given |
| `--delete` | Permanently delete duplicates |
| `--yes`, `-y` | Skip the confirmation prompt for `--delete` or `--relocate` |
| `--verbose` | Enable debug-level logging |