#!/usr/bin/env python3
"""
Create Google Fonts submission packages using custom metadata files.

Usage:
    python scripts/make_packages.py [--out OUTPUT_DIR]

The script reads custom METADATA and DESCRIPTION files from the release/
folder and creates zip packages for Heiti and Songti families.
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path


def create_family_package(
    family_name: str,
    family_prefix: str,
    input_dir: Path,
    release_dir: Path,
    output_dir: Path,
) -> Path:
    """Create a zip package for a font family.
    
    Args:
        family_name: Display name (e.g., "Heiti", "Songti")
        family_prefix: Prefix for files (e.g., "NanGuoHeitiPinyin", "NanGuoSongtiPinyin")
        input_dir: Directory containing TTF files
        release_dir: Directory containing custom METADATA and DESCRIPTION files
        output_dir: Output directory for the zip file
        
    Returns:
        Path to the created zip file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Output zip filename
    zip_name = f"NanGuo{family_name}Pinyin-GoogleFonts.zip"
    zip_path = output_dir / zip_name
    
    # Custom metadata files from release/
    metadata_file = release_dir / f"METADATA-{family_name}-Fonts.pb"
    description_file = release_dir / f"DESCRIPTION-{family_name}.en_us.html"
    ofl_file = release_dir / "OFL.txt"
    
    if not metadata_file.exists():
        raise FileNotFoundError(f"Missing {metadata_file}")
    if not description_file.exists():
        raise FileNotFoundError(f"Missing {description_file}")
    if not ofl_file.exists():
        raise FileNotFoundError(f"Missing {ofl_file}")
    
    # Collect all TTF files for this family
    ttf_files = sorted(input_dir.glob(f"{family_prefix}-*.ttf"))
    if not ttf_files:
        raise FileNotFoundError(f"No TTF files found for {family_prefix}")
    
    print(f"\nCreating {family_name} package: {zip_name}")
    print(f"  Found {len(ttf_files)} TTF files")
    
    # Create zip archive
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add TTF files
        for ttf_file in ttf_files:
            zf.write(ttf_file, arcname=ttf_file.name)
            print(f"    + {ttf_file.name}")
        
        # Add metadata files with standard names
        zf.write(metadata_file, arcname="METADATA.pb")
        print(f"    + METADATA.pb (from {metadata_file.name})")
        
        zf.write(description_file, arcname="DESCRIPTION.en_us.html")
        print(f"    + DESCRIPTION.en_us.html (from {description_file.name})")
        
        zf.write(ofl_file, arcname="OFL.txt")
        print(f"    + OFL.txt")
    
    zip_size = zip_path.stat().st_size / 1e6
    print(f"  Created: {zip_path.name}  ({zip_size:.1f} MB)")
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create Google Fonts submission packages for NanGuo Pinyin fonts"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent.parent / "release",
        help="Output directory (default: release/)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent.parent / "output",
        help="Base input directory containing heiti/ and songti/ subdirs",
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input)
    output_dir = Path(args.out)
    release_dir = output_dir  # Metadata files are in release/ alongside the output zips
    
    print("=" * 70)
    print("NanGuo Pinyin Fonts - Google Fonts Package Builder")
    print("=" * 70)
    
    # Create packages for both families
    families = [
        ("Heiti", "NanGuoHeitiPinyin", input_dir / "heiti"),
        ("Songti", "NanGuoSongtiPinyin", input_dir / "songti"),
    ]
    
    created_packages = []
    for display_name, prefix, family_input_dir in families:
        if not family_input_dir.exists():
            raise FileNotFoundError(f"Input directory not found: {family_input_dir}")
        
        zip_path = create_family_package(
            family_name=display_name,
            family_prefix=prefix,
            input_dir=family_input_dir,
            release_dir=release_dir,
            output_dir=output_dir,
        )
        created_packages.append(zip_path)
    
    print("\n" + "=" * 70)
    print(f"Successfully created {len(created_packages)} packages:")
    for pkg in created_packages:
        print(f"  ✓ {pkg}")
    print("=" * 70)


if __name__ == "__main__":
    main()
