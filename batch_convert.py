# /// script
# dependencies = [
#   "lupa",
#   "click",
#   "rich",
# ]
# ///

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

# Import the conversion functions from the main script
from koreader_lua_to_markdown import (
    parse_lua,
    generate_markdown,
    save_markdown,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()


def find_metadata_files(input_dir: Path) -> list[Path]:
    """
    Find all metadata.epub.lua files in the directory structure.

    Args:
        input_dir: Root directory to search

    Returns:
        List of paths to metadata.epub.lua files
    """
    metadata_files = []

    logger.info(f"Searching for metadata files in: {input_dir}")

    # Look for .sdr directories containing metadata.epub.lua
    for sdr_dir in input_dir.rglob("*.sdr"):
        metadata_file = sdr_dir / "metadata.epub.lua"
        if metadata_file.exists():
            metadata_files.append(metadata_file)

    logger.info(f"Found {len(metadata_files)} metadata files")
    return metadata_files


def batch_convert(input_dir: Path, output_dir: Path, verbose: bool = False) -> None:
    """
    Batch convert all KOReader metadata files to markdown.

    Args:
        input_dir: Input directory containing KOReader books
        output_dir: Output directory for markdown files
        verbose: Enable verbose logging
    """
    # Configure logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    try:
        # Find all metadata files
        metadata_files = find_metadata_files(input_dir)

        if not metadata_files:
            console.print("[yellow]No metadata.epub.lua files found in the input directory.[/yellow]")
            return

        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {output_dir}")

        # Create summary table
        table = Table(title="Batch Conversion Summary")
        table.add_column("Status", style="cyan")
        table.add_column("Count", style="magenta")
        table.add_column("Percentage", style="green")

        total_files = len(metadata_files)
        successful = 0
        failed = 0
        skipped = 0

        # Process files with progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:

            task = progress.add_task(f"Converting {total_files} files...", total=total_files)

            for metadata_file in metadata_files:
                try:
                    progress.update(task, description=f"Processing {metadata_file.parent.name}...")

                    # Parse the Lua file
                    metadata = parse_lua(metadata_file)

                    # Generate markdown content
                    markdown, timestamp = generate_markdown(metadata)

                    # Generate output filename
                    filename = f"{timestamp}.md"
                    output_path = output_dir / filename

                    # Check if file already exists
                    if output_path.exists():
                        logger.debug(f"File already exists, skipping: {output_path}")
                        skipped += 1
                        progress.advance(task)
                        continue

                    # Save the markdown
                    save_markdown(markdown, output_path)

                    successful += 1
                    logger.info(f"✅ Converted: {metadata_file.parent.name} -> {filename}")

                except Exception as e:
                    failed += 1
                    logger.error(f"❌ Failed to convert {metadata_file.parent.name}: {e}")
                    if verbose:
                        console.print(f"[red]Error details for {metadata_file.parent.name}: {e}[/red]")

                progress.advance(task)

        # Update summary table
        table.add_row("✅ Successful", str(successful), f"{(successful/total_files)*100:.1f}%")
        table.add_row("❌ Failed", str(failed), f"{(failed/total_files)*100:.1f}%")
        table.add_row("⏭️  Skipped", str(skipped), f"{(skipped/total_files)*100:.1f}%")
        table.add_row("📊 Total", str(total_files), "100%")

        # Print results
        console.print("\n")
        console.print(table)

        if failed > 0:
            console.print(f"\n[red]{failed} files failed to convert. Use --verbose for error details.[/red]")

        if successful > 0:
            console.print(f"\n[green]✅ Successfully converted {successful} files to {output_dir}[/green]")

    except Exception as e:
        logger.error(f"Batch conversion failed: {e}")
        console.print(f"[red]❌ Batch conversion failed: {e}[/red]")
        sys.exit(1)


@click.command()
@click.option(
    '--input', '-i',
    'input_dir',
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Input directory containing KOReader books with .sdr folders'
)
@click.option(
    '--output', '-o',
    'output_dir',
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help='Output directory for markdown files'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def main(input_dir: Path, output_dir: Path, verbose: bool) -> None:
    """
    Batch convert KOReader metadata files to markdown format.

    This script searches for all metadata.epub.lua files in .sdr subdirectories
    and converts them to markdown files using the conversion logic from
    koreader_lua_to_markdown.py.

    Examples:
        uv run batch_convert.py --input /path/to/books --output /path/to/output
        uv run batch_convert.py -i /path/to/books -o /path/to/output --verbose
    """
    console.print("[bold blue]KOReader Lua to Markdown - Batch Converter[/bold blue]\n")

    # Validate input directory
    if not input_dir.exists():
        console.print(f"[red]Input directory does not exist: {input_dir}[/red]")
        sys.exit(1)

    # Show conversion info
    console.print(f"📚 Input directory: {input_dir}")
    console.print(f"📝 Output directory: {output_dir}")
    console.print(f"🔍 Looking for metadata.epub.lua files in .sdr subdirectories...\n")

    # Run batch conversion
    batch_convert(input_dir, output_dir, verbose)


if __name__ == "__main__":
    main()