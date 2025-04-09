import os
import mimetypes
import magic
from typing import Dict, Tuple

# Initialize mimetypes with standard types
mimetypes.init()

# Define a comprehensive mapping of extensions to MIME types and icons
# This serves as our single source of truth
FILE_TYPE_MAP: Dict[str, Tuple[str, str]] = {
    # Documents
    'pdf': ('application/pdf', 'fa-solid fa-file-pdf'),
    'doc': ('application/msword', 'fa-solid fa-file-word'),
    'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'fa-solid fa-file-word'),
    'xls': ('application/vnd.ms-excel', 'fa-solid fa-file-excel'),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'fa-solid fa-file-excel'),
    'ppt': ('application/vnd.ms-powerpoint', 'fa-solid fa-file-powerpoint'),
    'pptx': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', 'fa-solid fa-file-powerpoint'),
    'txt': ('text/plain', 'fa-solid fa-file-lines'),
    'rtf': ('application/rtf', 'fa-solid fa-file-lines'),
    'md': ('text/markdown', 'fa-solid fa-file-lines'),
    'markdown': ('text/markdown', 'fa-solid fa-file-lines'),
    'csv': ('text/csv', 'fa-solid fa-file-csv'),
    
    # Documentation formats
    'swagger': ('application/x-swagger+json', 'fa-solid fa-file-code'),
    'openapi': ('application/x-openapi+json', 'fa-solid fa-file-code'),
    'wiki': ('text/x-wiki', 'fa-solid fa-file-lines'),
    'tex': ('application/x-tex', 'fa-solid fa-file-lines'),
    'rst': ('text/x-rst', 'fa-solid fa-file-lines'),
    'epub': ('application/epub+zip', 'fa-solid fa-book'),
    'asciidoc': ('text/x-asciidoc', 'fa-solid fa-file-lines'),
    'adoc': ('text/x-asciidoc', 'fa-solid fa-file-lines'),
    'docbook': ('application/docbook+xml', 'fa-solid fa-file-lines'),
    
    # Code files
    'html': ('text/html', 'fa-solid fa-file-code'),
    'htm': ('text/html', 'fa-solid fa-file-code'),
    'css': ('text/css', 'fa-solid fa-file-code'),
    'js': ('application/javascript', 'fa-solid fa-file-code'),
    'py': ('text/x-python', 'fa-solid fa-file-code'),
    'java': ('text/x-java', 'fa-solid fa-file-code'),
    'c': ('text/x-c', 'fa-solid fa-file-code'),
    'cpp': ('text/x-c++', 'fa-solid fa-file-code'),
    'h': ('text/x-c', 'fa-solid fa-file-code'),
    'php': ('application/x-php', 'fa-solid fa-file-code'),
    'rb': ('text/x-ruby', 'fa-solid fa-file-code'),
    'json': ('application/json', 'fa-solid fa-file-code'),
    'xml': ('application/xml', 'fa-solid fa-file-code'),
    'sql': ('text/x-sql', 'fa-solid fa-file-code'),
    'sh': ('application/x-sh', 'fa-solid fa-file-code'),
    'yaml': ('text/yaml', 'fa-solid fa-file-code'),
    'yml': ('text/yaml', 'fa-solid fa-file-code'),
    
    # Images
    'jpg': ('image/jpeg', 'fa-solid fa-file-image'),
    'jpeg': ('image/jpeg', 'fa-solid fa-file-image'),
    'png': ('image/png', 'fa-solid fa-file-image'),
    'gif': ('image/gif', 'fa-solid fa-file-image'),
    'bmp': ('image/bmp', 'fa-solid fa-file-image'),
    'svg': ('image/svg+xml', 'fa-solid fa-file-image'),
    'webp': ('image/webp', 'fa-solid fa-file-image'),
    
    # Audio
    'mp3': ('audio/mpeg', 'fa-solid fa-file-audio'),
    'wav': ('audio/wav', 'fa-solid fa-file-audio'),
    'ogg': ('audio/ogg', 'fa-solid fa-file-audio'),
    'flac': ('audio/flac', 'fa-solid fa-file-audio'),
    
    # Video
    'mp4': ('video/mp4', 'fa-solid fa-file-video'),
    'avi': ('video/x-msvideo', 'fa-solid fa-file-video'),
    'mov': ('video/quicktime', 'fa-solid fa-file-video'),
    'wmv': ('video/x-ms-wmv', 'fa-solid fa-file-video'),
    'mkv': ('video/x-matroska', 'fa-solid fa-file-video'),
    'webm': ('video/webm', 'fa-solid fa-file-video'),
    
    # Archives
    'zip': ('application/zip', 'fa-solid fa-file-zipper'),
    'rar': ('application/vnd.rar', 'fa-solid fa-file-zipper'),
    '7z': ('application/x-7z-compressed', 'fa-solid fa-file-zipper'),
    'tar': ('application/x-tar', 'fa-solid fa-file-zipper'),
    'gz': ('application/gzip', 'fa-solid fa-file-zipper'),
}

# Special case for directories
DIRECTORY_TYPE = ('inode/directory', 'fa-solid fa-folder')
# Default for unknown types
DEFAULT_TYPE = ('application/octet-stream', 'fa-solid fa-file')


def get_file_type_info(filepath: str, use_magic_fallback: bool = True) -> Tuple[str, str]:
    """
    Get the MIME type and icon for a file.
    
    Args:
        filepath: Path to the file
        use_magic_fallback: Whether to use magic library as fallback for unknown extensions
        
    Returns:
        Tuple of (mime_type, icon_class)
    """
    # Handle directories as a special case
    if os.path.isdir(filepath):
        return DIRECTORY_TYPE
    
    # Get extension (without the dot) and convert to lowercase
    _, ext = os.path.splitext(filepath)
    ext = ext.lower().lstrip('.')
    
    # First try our custom mapping
    if ext in FILE_TYPE_MAP:
        return FILE_TYPE_MAP[ext]
    
    # Next try the mimetypes module
    mime_type = mimetypes.guess_type(filepath)[0]
    if mime_type:
        # For known MIME types without custom icons, use a generic icon based on MIME category
        if mime_type.startswith('text/'):
            return (mime_type, 'fa-solid fa-file-lines')
        elif mime_type.startswith('image/'):
            return (mime_type, 'fa-solid fa-file-image')
        elif mime_type.startswith('audio/'):
            return (mime_type, 'fa-solid fa-file-audio')
        elif mime_type.startswith('video/'):
            return (mime_type, 'fa-solid fa-file-video')
        elif mime_type.startswith('application/'):
            if 'zip' in mime_type or 'compressed' in mime_type or 'archive' in mime_type:
                return (mime_type, 'fa-solid fa-file-zipper')
            elif any(x in mime_type for x in ['javascript', 'json', 'xml', 'yaml']):
                return (mime_type, 'fa-solid fa-file-code')
        # Return the MIME type with a generic file icon
        return (mime_type, 'fa-solid fa-file')
    
    # As a last resort, use magic to detect the MIME type
    if use_magic_fallback:
        try:
            detected_mime = magic.from_file(filepath, mime=True)
            
            # For text files detected by magic, try to be more specific based on extension
            if detected_mime == 'text/plain' and ext:
                # Check if this extension should be a specific text type
                for known_ext, (known_mime, icon) in FILE_TYPE_MAP.items():
                    if known_ext == ext and known_mime.startswith('text/'):
                        return (known_mime, icon)
            
            # For known MIME categories, use appropriate icons
            if detected_mime.startswith('text/'):
                return (detected_mime, 'fa-solid fa-file-lines')
            elif detected_mime.startswith('image/'):
                return (detected_mime, 'fa-solid fa-file-image')
            elif detected_mime.startswith('audio/'):
                return (detected_mime, 'fa-solid fa-file-audio')
            elif detected_mime.startswith('video/'):
                return (detected_mime, 'fa-solid fa-file-video')
            
            return (detected_mime, 'fa-solid fa-file')
        except Exception:
            # If magic fails, fall back to default
            return DEFAULT_TYPE
    
    # If all else fails, return default
    return DEFAULT_TYPE


def get_mime_type(filepath: str) -> str:
    """Get just the MIME type for a file."""
    return get_file_type_info(filepath)[0]


def get_file_icon(filepath: str) -> str:
    """Get just the icon class for a file."""
    return get_file_type_info(filepath)[1]


# For backward compatibility with existing code
def get_file_icon_by_name(filename: str) -> str:
    """
    Return the appropriate FontAwesome icon class for a given filename.
    This maintains compatibility with the existing function in jinja_extensions.py
    
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
    
    # Use our mapping
    if ext in FILE_TYPE_MAP:
        return FILE_TYPE_MAP[ext][1]
    
    # Default icon
    return "fa-solid fa-file"
def format_file_size(byte_size):
    """Format byte size to human readable format"""
    if byte_size is None:
        return "Unknown size"

    if byte_size < 1024:
        return f"{byte_size} bytes"
    elif byte_size < 1024 * 1024:
        return f"{byte_size / 1024:.1f} KB"
    elif byte_size < 1024 * 1024 * 1024:
        return f"{byte_size / (1024 * 1024):.1f} MB"
    else:
        return f"{byte_size / (1024 * 1024 * 1024):.1f} GB"
