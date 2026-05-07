import os
from pathlib import Path

WORKSPACE = Path(os.getenv("WORKSPACE_DIR", os.getcwd())).resolve()

def _safe_path(user_path: str) -> Path:
    target = (WORKSPACE / user_path).resolve()
    if WORKSPACE not in target.parents and target != WORKSPACE:
        raise ValueError(f"Access denied: '{user_path}' is outside the workspace.")
    return target

def read_file(path: str, encoding: str = "utf-8", max_chars: int = 5000) -> dict:
    result = {"success": False, "content": None, "error": None, "path": path, "truncated": False}
    try:
        if max_chars is not None and max_chars < 0:
            max_chars = None
        safe = _safe_path(path)
        raw = safe.read_text(encoding=encoding)
        if max_chars is None or len(raw) <= max_chars:
            result["content"] = raw
        else:
            marker = "\n...[output truncated]...\n"
            half = (max_chars - len(marker)) // 2
            if half <= 0:
                result["content"] = raw[:max_chars]
            else:
                result["content"] = raw[:half] + marker + raw[-half:]
            result["truncated"] = True
        result["success"] = True
    except Exception as e:
        result["error"] = str(e)
    return result

def write_file(path: str, content: str, encoding: str = "utf-8", overwrite: bool = False) -> dict:
    result = {"success": False, "content": None, "error": None, "path": path, "bytes_written": None}
    try:
        safe = _safe_path(path)
        if safe.exists() and not overwrite:
            result["error"] = "File already exists and overwrite=False"
            return result
        safe.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode(encoding)
        safe.write_bytes(data)
        result["success"] = True
        result["bytes_written"] = len(data)
    except Exception as e:
        result["error"] = str(e)
    return result

def edit_file(
    path: str,
    old_str: str,
    new_str: str,
    encoding: str = "utf-8",
    allow_multiple: bool = False
) -> dict:
    result = {
        "success": False,
        "content": None,
        "error": None,
        "path": path,
        "occurrences": 0,
        "replacements": 0
    }
    try:
        if old_str == "":
            result["error"] = "old_str cannot be empty"
            return result

        safe = _safe_path(path)
        text = safe.read_text(encoding=encoding)
        occ = text.count(old_str)
        result["occurrences"] = occ
        if occ == 0:
            result["error"] = "Substring not found"
            return result

        if occ > 1 and not allow_multiple:
            result["error"] = (
                "Substring appears multiple times. Set allow_multiple=True "
                "to replace all occurrences."
            )
            return result

        replacements = occ if allow_multiple else 1
        new_text = text.replace(old_str, new_str, replacements)
        safe.write_text(new_text, encoding=encoding)
        result["success"] = True
        result["replacements"] = replacements
    except Exception as e:
        result["error"] = str(e)
    return result
