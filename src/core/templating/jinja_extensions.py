from markdown2 import markdown

from src.utils.file_types import format_file_size as file_size_formatter, get_file_icon_by_name

def markdown2html(text: str):
    """Convert markdown text to HTML"""
    from src.main import logger
    logger.debug(f"Converting markdown to html: {text}")
    return markdown(text, extras={
        'breaks': {'on_newline': True},
        'fenced-code-blocks': {},
        'highlightjs-lang': {},
    })

def format_text_length(length: int) -> str:
    """Format text length to human readable format, 8k, 1M, 1G, etc."""

    if length < 1024:
        return f"{length} chars"

    elif length < 1024 * 1024:
        return f"{length / 1024:.1f} K"

    elif length < 1024 * 1024 * 1024:
        return f"{length / (1024 * 1024):.1f} M"


def format_cost_per_million(cost_param: int) -> str:
    """Convert cost from $/1k to $/1M"""
    if isinstance(cost_param, str):
        cost_param = float(cost_param)

    if cost_param == 0:
        return "0"

    return f"{(cost_param * 1000):.4f}"

def quote_plus(url: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(url)



def format_file_size(byte_size):
    """Format byte size to human readable format"""
    return file_size_formatter(byte_size)


def get_file_icon(filename):
    """
    Return the appropriate FontAwesome icon class for a given filename.

    Args:
        filename (str): The filename to get an icon for

    Returns:
        str: FontAwesome icon class
    """
    return get_file_icon_by_name(filename)
