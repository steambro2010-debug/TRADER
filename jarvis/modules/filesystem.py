from __future__ import annotations

from pathlib import Path
import shutil
from typing import Dict, Any


class FilesystemModule:
    def execute(self, intent: str, params: Dict[str, Any]) -> str:
        if intent == "create_folder":
            p = Path(params["path"])
            p.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {p}"
        if intent == "create_file":
            p = Path(params["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(params.get("content", ""), encoding="utf-8")
            return f"Created file: {p}"
        if intent == "move_file":
            src, dst = Path(params["src"]), Path(params["dst"])
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return f"Moved {src} to {dst}"
        if intent == "rename_file":
            src, new_name = Path(params["path"]), params["new_name"]
            dst = src.with_name(new_name)
            src.rename(dst)
            return f"Renamed {src} to {dst.name}"
        if intent == "delete_path":
            p = Path(params["path"])
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
            return f"Deleted {p}"
        raise ValueError(f"Unsupported filesystem intent: {intent}")
