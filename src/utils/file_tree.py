from typing import Dict, List, Any
from src.core.models import RootFile


def build_file_tree(files: List[RootFile]) -> Dict[str, Any]:
    """
    Build a nested tree structure from a list of RootFile objects.

    Args:
        files: List of RootFile objects with path attributes

    Returns:
        A nested dictionary representing the file tree structure
    """
    tree = {"name": "Root", "children": {}, "is_dir": True}

    for file in files:
        path_parts = file.path.split('/')
        current_level = tree["children"]

        # Process all directories in the path
        for i, part in enumerate(path_parts[:-1]):
            if part not in current_level:
                current_level[part] = {"name": part, "children": {}, "is_dir": True}
            current_level = current_level[part]["children"]

        # Add the file at the end
        filename = path_parts[-1]
        current_level[filename] = {
            "name": filename,
            "path": file.path,
            "is_dir": False,
            "file": file
        }

    return tree
