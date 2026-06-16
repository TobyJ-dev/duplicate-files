# duplicate-finder

A command-line tool to find and optionally remove duplicate files, 
with support for images and music files.

## Features

- Recursive directory scan
- Content-based duplicate detection via MD5 hashing
- Optional filtering by file type (images, music)
- CSV report export
- Safe staging mode and optional hard delete

## Requirements

Python 3.10+

## Installation

git clone <your-repo-url>
cd duplicate-finder
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

## Usage

python dedupe.py /path/to/dir
python dedupe.py /path/to/dir --type images
python dedupe.py /path/to/dir --type music
python dedupe.py /path/to/dir --type images --dry-run
python dedupe.py /path/to/dir --output report.csv
python dedupe.py /path/to/dir --delete --yes