"""Built-in filesystem search and read skill."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from core.orchestration.schemas import ContextPack
from core.skills.base import Skill

_SKIPPED_DIRS = {".git", ".venv", "node_modules", "__pycache__"}


class FilesystemMatch(BaseModel):
    path: str
    snippet: str


class FilesystemSearchReadInput(BaseModel):
    query: str
    cwd: str
    max_results: int = 20


class FilesystemSearchReadOutput(BaseModel):
    matches: list[FilesystemMatch] = Field(default_factory=list)


class FilesystemSearchReadSkill(Skill):
    """Recursively searches text files for a case-insensitive substring."""

    name = "filesystem.search_read"
    description = "Search files under a cwd and return matching snippets"
    side_effect = "read"
    input_model = FilesystemSearchReadInput
    output_model = FilesystemSearchReadOutput

    def run(
        self,
        input_data: FilesystemSearchReadInput,
        ctx: ContextPack,
    ) -> FilesystemSearchReadOutput:
        root = Path(input_data.cwd)
        query = input_data.query.lower().strip()
        results: list[FilesystemMatch] = []

        if not root.exists() or not root.is_dir() or not query:
            return FilesystemSearchReadOutput(matches=[])

        for current_root, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in _SKIPPED_DIRS]
            for file_name in files:
                path = Path(current_root) / file_name
                if path.is_symlink() or not path.is_file():
                    continue
                try:
                    content = path.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    # Skip unreadable/non-text files.
                    continue

                for line in content.splitlines():
                    if query in line.lower():
                        snippet = line.strip()
                        if len(snippet) > 200:
                            snippet = f"{snippet[:197]}..."
                        results.append(
                            FilesystemMatch(path=str(path), snippet=snippet)
                        )
                        break

                if len(results) >= input_data.max_results:
                    return FilesystemSearchReadOutput(matches=results)

        return FilesystemSearchReadOutput(matches=results)
