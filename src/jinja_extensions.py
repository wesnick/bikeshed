from markdown2 import markdown
import os

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

def model_select():
    from src.main import app
    registry = app.state.registry
    models = registry.list_models(True)

    return models

def quote_plus(url: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(url)



def format_file_size(byte_size):
    """Format byte size to human readable format"""
    if byte_size is None:
        return "Unknown size"

    if byte_size < 1024:
        return f"{byte_size} bytes"
    elif byte_size < 1024 * 1024:
        return f"{byte_size / 1024:.1f} KB"
    else:
        return f"{byte_size / (1024 * 1024):.1f} MB"

def get_file_icon(filename):
    """
    Return the appropriate FontAwesome icon class for a given filename.

    Args:
        filename (str): The filename to get an icon for

    Returns:
        str: FontAwesome icon class
    """
    if not filename:
        return "fa-solid fa-file"

    # Get the file extension (lowercase)
    _, ext = os.path.splitext(filename)
    ext = ext.lower().lstrip('.')

    # Map of file extensions to FontAwesome icons
    icon_map = {
        # Documents
        'pdf': 'fa-solid fa-file-pdf',
        'doc': 'fa-solid fa-file-word',
        'docx': 'fa-solid fa-file-word',
        'xls': 'fa-solid fa-file-excel',
        'xlsx': 'fa-solid fa-file-excel',
        'ppt': 'fa-solid fa-file-powerpoint',
        'pptx': 'fa-solid fa-file-powerpoint',
        'txt': 'fa-solid fa-file-lines',
        'rtf': 'fa-solid fa-file-lines',
        'md': 'fa-solid fa-file-lines',
        'csv': 'fa-solid fa-file-csv',

        # Images
        'jpg': 'fa-solid fa-file-image',
        'jpeg': 'fa-solid fa-file-image',
        'png': 'fa-solid fa-file-image',
        'gif': 'fa-solid fa-file-image',
        'bmp': 'fa-solid fa-file-image',
        'svg': 'fa-solid fa-file-image',
        'webp': 'fa-solid fa-file-image',

        # Audio
        'mp3': 'fa-solid fa-file-audio',
        'wav': 'fa-solid fa-file-audio',
        'ogg': 'fa-solid fa-file-audio',
        'flac': 'fa-solid fa-file-audio',

        # Video
        'mp4': 'fa-solid fa-file-video',
        'avi': 'fa-solid fa-file-video',
        'mov': 'fa-solid fa-file-video',
        'wmv': 'fa-solid fa-file-video',
        'mkv': 'fa-solid fa-file-video',
        'webm': 'fa-solid fa-file-video',

        # Archives
        'zip': 'fa-solid fa-file-zipper',
        'rar': 'fa-solid fa-file-zipper',
        '7z': 'fa-solid fa-file-zipper',
        'tar': 'fa-solid fa-file-zipper',
        'gz': 'fa-solid fa-file-zipper',

        # Code
        'html': 'fa-solid fa-file-code',
        'css': 'fa-solid fa-file-code',
        'js': 'fa-solid fa-file-code',
        'py': 'fa-solid fa-file-code',
        'java': 'fa-solid fa-file-code',
        'c': 'fa-solid fa-file-code',
        'cpp': 'fa-solid fa-file-code',
        'h': 'fa-solid fa-file-code',
        'php': 'fa-solid fa-file-code',
        'rb': 'fa-solid fa-file-code',
        'json': 'fa-solid fa-file-code',
        'xml': 'fa-solid fa-file-code',
        'sql': 'fa-solid fa-file-code',
        'sh': 'fa-solid fa-file-code',
        'yaml': 'fa-solid fa-file-code',
        'yml': 'fa-solid fa-file-code',
    }

    # Return the specific icon if found, otherwise return a generic file icon
    return icon_map.get(ext, 'fa-solid fa-file')
