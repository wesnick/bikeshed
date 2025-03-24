from markdown2 import markdown

def markdown2html(text: str):
    """Convert markdown text to HTML"""
    from src.main import logger
    logger.debug(f"Converting markdown to html: {text}")
    return markdown(text, extras={
        'breaks': {'on_newline': True},
        'fenced-code-blocks': {},
        'highlightjs-lang': {},
    })

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
