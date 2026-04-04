#!/usr/bin/env python3
"""Build a QGIS plugin zip from the svgexport plugin folder."""

import argparse
import configparser
import os
import zipfile

PLUGIN_FOLDER_NAME = "svgexport"
EXCLUDE_DIRS = {"__pycache__", ".git"}
EXCLUDE_EXTENSIONS = {".pyc", ".pyo"}


def is_excluded(path, rel_path):
    basename = os.path.basename(path)
    if basename in EXCLUDE_DIRS:
        return True
    if os.path.isdir(path):
        return False
    _, ext = os.path.splitext(path)
    if ext.lower() in EXCLUDE_EXTENSIONS:
        return True
    return False


def build_zip(source_dir, output_path):
    if not os.path.isdir(source_dir):
        raise FileNotFoundError(f"Plugin source directory not found: {source_dir}")

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for folder, dirs, files in os.walk(source_dir):
            # remove excluded directories in-place so os.walk skips them
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for filename in files:
                full_path = os.path.join(folder, filename)
                if is_excluded(full_path, os.path.relpath(full_path, source_dir)):
                    continue

                rel_path = os.path.relpath(full_path, source_dir)
                archive_name = os.path.join(PLUGIN_FOLDER_NAME, rel_path).replace("\\", "/")
                archive.write(full_path, archive_name)

    return output_path


def read_version(source_dir):
    metadata_path = os.path.join(source_dir, "metadata.txt")
    config = configparser.ConfigParser()
    config.read(metadata_path)
    return config["general"]["version"]


def parse_args():
    parser = argparse.ArgumentParser(description="Create a QGIS plugin zip for svgexport.")
    parser.add_argument(
        "--source",
        default=os.path.join(os.path.dirname(__file__), PLUGIN_FOLDER_NAME),
        help="Path to the plugin source folder (default: ./svgexport)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output zip file path (default: ./svgexport.<version>.zip)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    source_dir = os.path.abspath(args.source)
    if args.output is None:
        version = read_version(source_dir)
        default_name = f"{PLUGIN_FOLDER_NAME}.{version}.zip"
        args.output = os.path.join(os.path.dirname(__file__), default_name)
    output_path = os.path.abspath(args.output)

    if os.path.exists(output_path) and not args.force:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Use --force to overwrite."
        )

    output = build_zip(source_dir, output_path)
    print(f"Created plugin zip: {output}")


if __name__ == "__main__":
    main()
