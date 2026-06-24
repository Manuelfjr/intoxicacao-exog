"""
This module provides utility functions for the regression notebooks.
"""

import sys
from pathlib import Path
from typing import Optional


def set_root(level: int = 1, library: Optional[str] = None) -> Path:
    """Set the root directory of the project.

    Parameters:
    -----------
    level : int, optional
        The number of parent directories to go up from the current file's directory.
        Default is 1, which means the immediate parent directory.

    Returns:
    --------
    Path
        The path to the root directory of the project.

    Examples:
    ---------
    >>> set_root()
    PosixPath('/user/dir/path/root/project-path')

    >>> set_root(2)
    PosixPath('/user/dir/path/root')

    """
    for i in range(level):
        if i == 0:
            PROJECT_DIR: Path = Path(__file__).parent
        else:
            PROJECT_DIR: Path = PROJECT_DIR.parent
    sys.path.append(str(PROJECT_DIR))

    if library is not None:
        sys.path.append(str(PROJECT_DIR / library))
    return PROJECT_DIR
