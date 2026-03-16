"""Tests for the import-aware context resolver."""

from __future__ import annotations

import textwrap

from agentforge.rag.import_resolver import (
    _extract_js_imports,
    _extract_python_imports,
    resolve_import_context,
)


class TestPythonImportExtraction:
    """Test Python import parsing."""

    def test_simple_import(self):
        code = "import os"
        assert _extract_python_imports(code) == ["os"]

    def test_from_import(self):
        code = "from pathlib import Path"
        assert _extract_python_imports(code) == ["pathlib"]

    def test_dotted_import(self):
        code = "from agentforge.models.schemas import ReviewRequest"
        assert _extract_python_imports(code) == ["agentforge.models.schemas"]

    def test_multiple_imports(self):
        code = textwrap.dedent("""\
            import os
            import json
            from pathlib import Path
            from agentforge.config import GOOGLE_API_KEY
        """)
        result = _extract_python_imports(code)
        assert "os" in result
        assert "json" in result
        assert "pathlib" in result
        assert "agentforge.config" in result

    def test_syntax_error_falls_back_to_regex(self):
        code = "from foo import bar\nthis is not valid python {{{"
        result = _extract_python_imports(code)
        assert "foo" in result

    def test_no_imports(self):
        code = "x = 1\ny = 2"
        assert _extract_python_imports(code) == []


class TestJSImportExtraction:
    """Test JavaScript/TypeScript import parsing."""

    def test_es6_import(self):
        code = "import { useState } from 'react'"
        result = _extract_js_imports(code)
        assert "react" in result

    def test_require(self):
        code = "const express = require('express')"
        result = _extract_js_imports(code)
        assert "express" in result

    def test_relative_import(self):
        code = "import { helper } from './utils/helper'"
        result = _extract_js_imports(code)
        assert "./utils/helper" in result


class TestResolveImportContext:
    """Test the full import resolution pipeline."""

    def test_resolves_local_file(self, tmp_path):
        # Create a simple project structure
        main_file = tmp_path / "main.py"
        utils_file = tmp_path / "utils.py"

        utils_file.write_text("def helper():\n    return 42\n")
        main_code = "from utils import helper\n\nresult = helper()"

        context = resolve_import_context(
            code=main_code,
            filename=str(main_file),
            search_roots=[str(tmp_path)],
        )

        assert "utils.py" in context
        assert "def helper" in context

    def test_no_results_for_stdlib(self, tmp_path):
        code = "import os\nimport json"
        context = resolve_import_context(
            code=code,
            filename=str(tmp_path / "test.py"),
            search_roots=[str(tmp_path)],
        )
        # os and json are stdlib — won't be found on disk at search_roots
        assert context == ""

    def test_empty_for_no_imports(self, tmp_path):
        code = "x = 1"
        context = resolve_import_context(
            code=code,
            filename=str(tmp_path / "test.py"),
        )
        assert context == ""
