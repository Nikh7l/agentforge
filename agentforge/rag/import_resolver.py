"""Import-aware context resolver — parses imports and fetches related source files."""

from __future__ import annotations

import ast
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Max characters of context to include from a single imported file
MAX_FILE_CONTEXT = 3000
# Max total context characters
MAX_TOTAL_CONTEXT = 15000


def resolve_import_context(
    code: str,
    filename: str,
    search_roots: list[str] | None = None,
) -> str:
    """Parse imports from the code and fetch related source files.

    This provides agents with genuine architectural context — they can see
    how the reviewed file connects to the rest of the codebase.

    Args:
        code: The source code being reviewed.
        filename: Name of the file being reviewed.
        search_roots: Directories to search for imported modules.
                      If None, uses the parent directory of filename.

    Returns:
        A formatted string of imported file contents for agent context.
    """
    language = _detect_language(filename)
    imports = _extract_imports(code, language)

    if not imports:
        return ""

    # Build search paths
    if search_roots:
        roots = [Path(r).resolve() for r in search_roots]
    else:
        file_path = Path(filename).resolve()
        roots = [file_path.parent]
        # Also try parent directories (for package-relative imports)
        if file_path.parent.parent.exists():
            roots.append(file_path.parent.parent)

    # Resolve imports to actual files
    resolved_files = _resolve_imports_to_files(imports, roots, language)

    if not resolved_files:
        return ""

    # Build context string
    sections = []
    total_chars = 0

    for import_name, filepath in resolved_files.items():
        if total_chars >= MAX_TOTAL_CONTEXT:
            break

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
            truncated = content[:MAX_FILE_CONTEXT]
            if len(content) > MAX_FILE_CONTEXT:
                truncated += f"\n# ... ({len(content) - MAX_FILE_CONTEXT} more characters truncated)"

            sections.append(f"### Imported: `{import_name}` → {filepath.name}\n```\n{truncated}\n```")
            total_chars += len(truncated)
        except Exception as e:
            logger.debug("Could not read %s: %s", filepath, e)
            continue

    if not sections:
        return ""

    header = f"## Related Files (imported by {Path(filename).name})\n"
    return header + "\n\n".join(sections)


def _detect_language(filename: str) -> str:
    """Detect programming language from file extension."""
    ext = Path(filename).suffix.lower()
    return {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".cpp": "cpp",
        ".c": "c",
    }.get(ext, "unknown")


def _extract_imports(code: str, language: str) -> list[str]:
    """Extract import module names from source code."""
    if language == "python":
        return _extract_python_imports(code)
    elif language in ("javascript", "typescript"):
        return _extract_js_imports(code)
    elif language == "go":
        return _extract_go_imports(code)
    elif language == "java":
        return _extract_java_imports(code)
    return []


def _extract_python_imports(code: str) -> list[str]:
    """Parse Python imports using the AST for accuracy."""
    modules = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
    except SyntaxError:
        # Fallback to regex for unparseable code
        for match in re.finditer(r"^\s*(?:from|import)\s+([\w.]+)", code, re.MULTILINE):
            modules.append(match.group(1))
    return modules


def _extract_js_imports(code: str) -> list[str]:
    """Extract JavaScript/TypeScript imports via regex."""
    modules = []
    # import ... from 'module'
    for match in re.finditer(r"""(?:import|require)\s*\(?[^'"]*['"]([^'"]+)['"]""", code):
        modules.append(match.group(1))
    return modules


def _extract_go_imports(code: str) -> list[str]:
    """Extract Go import paths."""
    modules = []
    for match in re.finditer(r'"([^"]+)"', code):
        path = match.group(1)
        if "/" in path:  # Skip stdlib short names
            modules.append(path)
    return modules


def _extract_java_imports(code: str) -> list[str]:
    """Extract Java import statements."""
    modules = []
    for match in re.finditer(r"^\s*import\s+([\w.]+);", code, re.MULTILINE):
        modules.append(match.group(1))
    return modules


def _resolve_imports_to_files(
    imports: list[str],
    search_roots: list[Path],
    language: str,
) -> dict[str, Path]:
    """Map import names to actual file paths on disk."""
    resolved: dict[str, Path] = {}

    for import_name in imports:
        filepath = _find_import_file(import_name, search_roots, language)
        if filepath:
            resolved[import_name] = filepath

    return resolved


def _find_import_file(import_name: str, search_roots: list[Path], language: str) -> Path | None:
    """Find the source file for a single import."""
    if language == "python":
        # Convert dotted module path to file path: foo.bar.baz → foo/bar/baz.py
        parts = import_name.split(".")
        candidates = [
            Path(*parts).with_suffix(".py"),
            Path(*parts) / "__init__.py",
            # Try just the last component (for relative-style imports)
            Path(parts[-1]).with_suffix(".py"),
        ]
    elif language in ("javascript", "typescript"):
        # ./utils → utils.js, utils.ts, utils/index.js
        clean = import_name.lstrip("./")
        candidates = [
            Path(clean).with_suffix(".js"),
            Path(clean).with_suffix(".ts"),
            Path(clean).with_suffix(".jsx"),
            Path(clean).with_suffix(".tsx"),
            Path(clean) / "index.js",
            Path(clean) / "index.ts",
        ]
    elif language == "go":
        parts = import_name.split("/")
        candidates = [Path(*parts)]
    elif language == "java":
        parts = import_name.split(".")
        candidates = [Path(*parts).with_suffix(".java")]
    else:
        return None

    for root in search_roots:
        for candidate in candidates:
            full_path = root / candidate
            if full_path.is_file():
                return full_path.resolve()

    return None
