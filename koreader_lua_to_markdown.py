# /// script
# dependencies = [
#   "lupa",
#   "click",
# ]
# ///

import logging
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import click
from lupa import LuaRuntime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_lua(file_path: Path) -> Dict[str, Any]:
    """
    Parse a Lua file containing KOReader metadata.

    Args:
        file_path: Path to the Lua file

    Returns:
        Dictionary containing the parsed metadata

    Raises:
        FileNotFoundError: If the Lua file doesn't exist
        ValueError: If the Lua content cannot be parsed
    """
    logger.info(f"Parsing Lua file: {file_path}")

    if not file_path.exists():
        raise FileNotFoundError(f"Lua file not found: {file_path}")

    try:
        lua = LuaRuntime(unpack_returned_tuples=True)
        with open(file_path, 'r', encoding='utf-8') as file:
            lua_content = file.read()

        wrapped_content = f"function() {lua_content} end"
        metadata = lua.eval(wrapped_content)()

        logger.info("Successfully parsed Lua file")
        return metadata

    except Exception as e:
        logger.error(f"Failed to parse Lua file {file_path}: {e}")
        raise ValueError(f"Failed to parse Lua file: {e}")


def generate_markdown(metadata: Dict[str, Any]) -> Tuple[str, str]:
    """
    Generate markdown content from KOReader metadata with YAML frontmatter.

    Args:
        metadata: Dictionary containing KOReader metadata

    Returns:
        Tuple of (markdown_content, timestamp_string)
    """
    logger.info("Generating markdown content")

    try:
        # Get stats from metadata
        stats = {}
        if hasattr(metadata, '__getitem__') and 'stats' in metadata:
            stats = metadata['stats']

        # Extract title and authors from stats
        title = stats['title'] if 'title' in stats else 'Unknown Title'
        authors = stats['authors'] if 'authors' in stats else 'Unknown Author'

        # Extract rating from summary
        rating = None
        if hasattr(metadata, '__getitem__') and 'summary' in metadata:
            summary = metadata['summary']
            if 'rating' in summary:
                rating = summary['rating']

        # Parse author name
        lastname, firstname = parse_author_name(authors)

        # Get timestamps from bookmarks
        created_at = None
        updated_at = None
        bookmarks = metadata['bookmarks'] if 'bookmarks' in metadata else {}
        if bookmarks:
            # Get all bookmarks
            bookmark_list = []
            if hasattr(bookmarks, 'values'):
                bookmark_list = list(bookmarks.values())
            elif hasattr(bookmarks, '__iter__'):
                bookmark_list = list(bookmarks)

            if bookmark_list:
                # Get first bookmark datetime for created_at
                first_bookmark = bookmark_list[0]
                if 'datetime' in first_bookmark:
                    created_at = first_bookmark['datetime']

                # Get last bookmark datetime for updated_at
                last_bookmark = bookmark_list[-1]
                if 'datetime' in last_bookmark:
                    updated_at = last_bookmark['datetime']

        # Generate timestamp for filename from created_at
        timestamp = None
        if created_at:
            timestamp = parse_bookmark_datetime(created_at)

        # Fallback to current time if no bookmark datetime found
        if timestamp is None:
            timestamp = generate_timestamp()

        # Generate YAML frontmatter
        yaml_frontmatter = f"""---
tags: [buch, gelesen, highlights]
title: {title}
author: {lastname}, {firstname}"""

        if rating is not None:
            yaml_frontmatter += f"\nrating: {rating}"

        if created_at:
            date_created = format_date_for_yaml(created_at)
            yaml_frontmatter += f"\ndate_created: {date_created}"

        if updated_at:
            date_updated = format_date_for_yaml(updated_at)
            yaml_frontmatter += f"\ndate_updated: {date_updated}"

        yaml_frontmatter += "\n---\n\n"

        # Generate intro text
        intro_text = f"Highlights für das Buch {title} von {firstname} {lastname}\n\n"

        # Generate highlights content
        highlights_content = ""
        bookmarks = metadata['bookmarks'] if 'bookmarks' in metadata else {}

        # Process bookmarks
        bookmark_list = []
        if hasattr(bookmarks, 'values'):
            bookmark_list = list(bookmarks.values())
        elif hasattr(bookmarks, '__iter__'):
            bookmark_list = list(bookmarks)

        for bookmark in reversed(bookmark_list):
            if 'notes' not in bookmark or not bookmark['notes'].strip():
                continue

            # Add the highlighted text as a blockquote
            highlights_content += f"> {bookmark['notes']}\n\n"

            # Add annotations if present
            if 'text' in bookmark and bookmark['text'].strip():
                highlights_content += f"Own thought:  \n{bookmark['text']}\n\n"

            highlights_content += "---\n\n"

        # Combine all parts
        md = yaml_frontmatter + intro_text + highlights_content.strip()

        logger.info("Successfully generated markdown")
        return md, timestamp

    except Exception as e:
        logger.error(f"Failed to generate markdown: {e}")
        raise ValueError(f"Failed to generate markdown: {e}")


def slugify(text: str) -> str:
    """
    Convert text to a URL-friendly slug.

    Args:
        text: Text to slugify

    Returns:
        Slugified string
    """
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text)
    return text.strip('-')


def generate_timestamp() -> str:
    """
    Generate timestamp in YYMMDDHHMM format.

    Returns:
        Timestamp string
    """
    return datetime.now().strftime("%y%m%d%H%M")


def parse_bookmark_datetime(datetime_str: str) -> str:
    """
    Parse bookmark datetime string and convert to YYMMDDHHMM format.

    Args:
        datetime_str: Datetime string in format "YYYY-MM-DD HH:MM:SS"

    Returns:
        Timestamp string in YYMMDDHHMM format
    """
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%y%m%d%H%M")
    except ValueError:
        logger.warning(f"Failed to parse datetime: {datetime_str}, using current time")
        return generate_timestamp()


def format_date_for_yaml(datetime_str: str) -> str:
    """
    Format datetime string to YYYY-MM-DD format for YAML frontmatter.

    Args:
        datetime_str: Datetime string in format "YYYY-MM-DD HH:MM:SS"

    Returns:
        Date string in YYYY-MM-DD format
    """
    try:
        dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        logger.warning(f"Failed to parse datetime: {datetime_str}, using current date")
        return datetime.now().strftime("%Y-%m-%d")


def parse_author_name(author_text: str) -> Tuple[str, str]:
    """
    Parse author name into lastname and firstname.

    Args:
        author_text: Raw author text from metadata

    Returns:
        Tuple of (lastname, firstname)
    """
    # Handle common formats like "Doe, John" or "John Doe"
    if ',' in author_text:
        parts = [p.strip() for p in author_text.split(',', 1)]
        lastname = parts[0]
        firstname = parts[1] if len(parts) > 1 else ''
    else:
        parts = author_text.strip().split()
        if len(parts) > 1:
            lastname = parts[-1]
            firstname = ' '.join(parts[:-1])
        else:
            lastname = author_text
            firstname = ''

    return lastname.strip(), firstname.strip()


def save_markdown(markdown: str, output_path: Path) -> None:
    """
    Save markdown content to a file.

    Args:
        markdown: Markdown content to save
        output_path: Path where to save the file
    """
    logger.info(f"Saving markdown to: {output_path}")

    try:
        # Create parent directories if they don't exist
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown)

        logger.info(f"Successfully saved markdown to {output_path}")

    except Exception as e:
        logger.error(f"Failed to save markdown to {output_path}: {e}")
        raise IOError(f"Failed to save markdown: {e}")


@click.command()
@click.argument(
    'lua_file',
    type=click.Path(exists=True, path_type=Path, dir_okay=False)
)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Output file path. If not specified, uses slugified title in current directory.'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Enable verbose logging'
)
def main(lua_file: Path, output: Optional[Path], verbose: bool) -> None:
    """
    Convert KOReader Lua metadata file to markdown format.

    LUA_FILE: Path to the KOReader Lua metadata file to convert.
    """
    # Configure logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    try:
        # Parse the Lua file
        metadata = parse_lua(lua_file)

        # Generate markdown content
        markdown, timestamp = generate_markdown(metadata)

        # Determine output path
        if output is None:
            filename = f"{timestamp}.md"
            output = Path(filename)
            logger.info(f"Using timestamp-based output filename: {output}")

        # Save the markdown
        save_markdown(markdown, output)

        click.echo(f"✅ Markdown saved to: {output}")

    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
