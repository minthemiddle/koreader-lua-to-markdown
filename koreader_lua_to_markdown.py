# /// script
# dependencies = [
#   "lupa",
#   "click",
#   "toml",
# ]
# ///

import logging
import sys
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import click
import toml
from lupa import LuaRuntime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Default configuration
DEFAULT_CONFIG = {
    "output": {
        "filename_template": "{timestamp}.md",
    },
    "templates": {
        "yaml_frontmatter": """---
tags: [buch, gelesen, highlights]
title: {title}
author: {lastname}, {firstname}{rating}{note}{date_created}{date_updated}
---

""",
        "intro": "Highlights für das Buch {title} von {firstname} {lastname}",
        "summary_note": "> {note}",
        "highlight": "> {text}",
        "annotation": "Eigener Gedanke{page}: {annotation}{time}",
        "separator": "---",
    }
}


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load configuration from TOML file.

    Args:
        config_path: Path to configuration file

    Returns:
        Configuration dictionary
    """
    if config_path is None:
        # Look for config in current directory
        config_path = Path("koreader_converter.toml")

    if not config_path.exists():
        logger.debug(f"No config file found at {config_path}, using defaults")
        return DEFAULT_CONFIG

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = toml.load(f)
        logger.info(f"Loaded configuration from {config_path}")

        # Deep merge with defaults to ensure all required keys exist
        result = DEFAULT_CONFIG.copy()

        # Merge output section
        if 'output' in config:
            result['output'].update(config['output'])

        # Merge templates section
        if 'templates' in config:
            result['templates'].update(config['templates'])

        return result
    except Exception as e:
        logger.error(f"Failed to load config from {config_path}: {e}")
        return DEFAULT_CONFIG


def format_template(template: str, **kwargs) -> str:
    """
    Format a template string with provided variables.

    Args:
        template: Template string with placeholders
        **kwargs: Variables to substitute

    Returns:
        Formatted string
    """
    try:
        # Handle special formatting for page and time in annotations
        formatted_kwargs = {}
        for key, value in kwargs.items():
            if key == 'page' and value:
                formatted_kwargs[key] = f" (Seite {value})"
            elif key == 'time' and value:
                formatted_kwargs[key] = f" @ {value}"
            else:
                formatted_kwargs[key] = value

        # Format the template
        result = template.format(**formatted_kwargs)

        # Remove lines that contain only empty placeholders (for YAML)
        lines = result.split('\n')
        cleaned_lines = []
        for line in lines:
            # Skip lines that have empty field values (like "rating: " or "note: ")
            if not line.strip().endswith(':') or not line.strip().endswith(': '):
                cleaned_lines.append(line)

        return '\n'.join(cleaned_lines)
    except KeyError as e:
        logger.warning(f"Missing placeholder in template: {e}")
        return template


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


def generate_markdown(metadata: Dict[str, Any], config: Dict[str, Any] = None) -> Tuple[str, str]:
    """
    Generate markdown content from KOReader metadata with YAML frontmatter.

    Args:
        metadata: Dictionary containing KOReader metadata
        config: Configuration dictionary with templates

    Returns:
        Tuple of (markdown_content, timestamp_string)
    """
    if config is None:
        config = DEFAULT_CONFIG
    logger.info("Generating markdown content")

    try:
        # Get stats from metadata
        stats = {}
        if hasattr(metadata, '__getitem__') and 'stats' in metadata:
            stats = metadata['stats']

        # Extract title and authors from stats
        title = stats['title'] if 'title' in stats else 'Unknown Title'
        authors = stats['authors'] if 'authors' in stats else 'Unknown Author'

        # Extract rating and note from summary
        rating = None
        summary_note = None
        if hasattr(metadata, '__getitem__') and 'summary' in metadata:
            summary = metadata['summary']
            if 'rating' in summary:
                rating = summary['rating']
            if 'note' in summary:
                summary_note = summary['note']

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

        # Generate YAML frontmatter using template
        templates = config['templates']
        rating_value = rating if rating is not None else ""
        note_value = summary_note if summary_note else ""
        date_created_value = format_date_for_yaml(created_at) if created_at else ""
        date_updated_value = format_date_for_yaml(updated_at) if updated_at else ""

        yaml_frontmatter = format_template(
            templates['yaml_frontmatter'],
            title=title,
            lastname=lastname,
            firstname=firstname,
            rating=rating_value,
            note=note_value,
            date_created=date_created_value,
            date_updated=date_updated_value
        )

        # Generate intro text using template
        intro_text = format_template(
            templates['intro'],
            title=title,
            firstname=firstname,
            lastname=lastname
        )

        if summary_note:
            intro_text += "\n\n" + format_template(
                templates['summary_note'],
                note=summary_note
            )
        intro_text += "\n\n"

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

            # Add the highlighted text using template
            highlights_content += format_template(
                templates['highlight'],
                text=bookmark['notes']
            ) + "\n\n"

            # Add annotations if present
            if 'text' in bookmark and bookmark['text'].strip():
                # Parse annotation text to extract page and timestamp
                annotation_data = parse_annotation_text(bookmark['text'])

                highlights_content += format_template(
                    templates['annotation'],
                    annotation=annotation_data['text'],
                    page=annotation_data['page'],
                    time=annotation_data['timestamp']
                ) + "\n\n"

            highlights_content += templates['separator'] + "\n\n"

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


def parse_annotation_text(annotation_text: str) -> Dict[str, str]:
    """
    Parse KOReader annotation text to extract page number, timestamp, and clean text.

    Args:
        annotation_text: Raw annotation text from KOReader

    Returns:
        Dictionary with 'page', 'text', and 'timestamp' keys
    """
    result = {
        'page': '',
        'text': annotation_text,
        'timestamp': ''
    }

    # Pattern: "Page XXX actual text @ YYYY-MM-DD HH:MM:SS"
    import re

    # Match page pattern
    page_match = re.match(r'Page\s+(\d+)\s+(.*)', annotation_text)
    if page_match:
        result['page'] = page_match.group(1)
        remaining_text = page_match.group(2)

        # Match timestamp pattern
        timestamp_match = re.search(r'(.*)\s+@\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})$', remaining_text)
        if timestamp_match:
            result['text'] = timestamp_match.group(1).strip()
            result['timestamp'] = timestamp_match.group(2)
        else:
            result['text'] = remaining_text.strip()

    return result


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
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path, dir_okay=False),
    help='Path to TOML configuration file'
)
def main(lua_file: Path, output: Optional[Path], verbose: bool, config: Optional[Path]) -> None:
    """
    Convert KOReader Lua metadata file to markdown format.

    LUA_FILE: Path to the KOReader Lua metadata file to convert.
    """
    # Configure logging level
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")

    try:
        # Load configuration
        config = load_config(config)

        # Parse the Lua file
        metadata = parse_lua(lua_file)

        # Generate markdown content
        markdown, timestamp = generate_markdown(metadata, config)

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
