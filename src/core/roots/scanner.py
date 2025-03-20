import os
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from sqlalchemy import select, create_engine
from sqlalchemy.orm import Session


class FileScanner:

    async def scan_directory(self, directory_path: str) -> None:
        """
        Recursively scan a directory and store file information in the database
        """
        directory_path = os.path.abspath(directory_path)
        directory = Path(directory_path)

