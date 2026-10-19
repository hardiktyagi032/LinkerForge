"""Inspect the released TransDFL source archive for residue-label handling."""

import hashlib
import zipfile
from pathlib import Path


PATH = Path("artifacts/transdfl-benchmark-original/TransDFL_source_code.zip")


def main() -> None:
    print("sha256", hashlib.sha256(PATH.read_bytes()).hexdigest())
    with zipfile.ZipFile(PATH) as archive:
        readme = archive.read("TransDFL_source_code/README").decode(errors="replace")
        print("README\n", readme[:3000])
        for name in archive.namelist():
            if name.startswith("__MACOSX") or not name.endswith(".py"):
                continue
            lines = archive.read(name).decode(errors="replace").splitlines()
            for i, line in enumerate(lines):
                if any(token in line for token in ("'x'", '"x"', "label_mask", "!= 'x'", "!= \"x\"")):
                    print(f"{name}:{i + 1}: {line.strip()[:220]}")


if __name__ == "__main__":
    main()
