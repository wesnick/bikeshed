from typing import Dict, List, Any
from src.core.models import RootFile


def build_file_tree(files: List[RootFile]) -> Dict[str, Any]:
    """
    Build a nested tree structure from a list of RootFile objects,
    where RootFiles can represent both files and directories.

    Args:
        files: List of RootFile objects with path attributes.
               Directory RootFiles should have mime_type='inode/directory'.

    Returns:
        A nested dictionary representing the file tree structure.
        Each node contains 'name', 'is_dir', 'children' (for dirs),
        and optionally 'file' (the corresponding RootFile object) and 'path' (for files).
    """
    tree = {"name": "Root", "children": {}, "is_dir": True, "file": None} # Root node

    for file in files:
        # Normalize path, split, and filter empty parts
        path_parts = [part for part in file.path.strip('/').split('/') if part]
        if not path_parts: # Skip if path is empty or just '/'
            continue

        current_level = tree["children"]

        for i, part in enumerate(path_parts):
            is_last_part = (i == len(path_parts) - 1)

            if part not in current_level:
                # Node doesn't exist, create it
                if is_last_part:
                    # This node corresponds directly to the current RootFile
                    if file.mime_type == 'inode/directory':
                        new_node = {"name": part, "children": {}, "is_dir": True, "file": file}
                    else:
                        new_node = {"name": part, "path": file.path, "is_dir": False, "file": file}
                    current_level[part] = new_node
                else:
                    # This is an intermediate directory path part, create placeholder
                    current_level[part] = {"name": part, "children": {}, "is_dir": True, "file": None}
            else:
                # Node exists, potentially update it if this is the last part
                if is_last_part:
                    existing_node = current_level[part]
                    if file.mime_type == 'inode/directory':
                        # Update existing node to be a directory, assign the file
                        existing_node["is_dir"] = True
                        existing_node["file"] = file
                        if "children" not in existing_node: # Ensure children dict exists
                            existing_node["children"] = {}
                        existing_node.pop("path", None) # Remove file-specific attribute
                    else:
                        # Update existing node to be a file, assign the file
                        existing_node["is_dir"] = False
                        existing_node["file"] = file
                        existing_node["path"] = file.path
                        existing_node.pop("children", None) # Remove directory-specific attribute

            # Move to the next level for the next part, ensuring the current node is a directory
            if not is_last_part:
                 current_node = current_level[part]
                 # Ensure the node we are descending into is marked as a directory
                 current_node["is_dir"] = True
                 if "children" not in current_node:
                     current_node["children"] = {}
                 # Remove file-specific attributes if they were somehow assigned before
                 current_node.pop("path", None)
                 current_level = current_node["children"]

    return tree
