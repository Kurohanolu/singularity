"""Verify the distribution repository and the bytes staged or served by Pages."""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

PUBLIC_REPO = "Kurohanolu/singularity"
BASE_URL = "https://kurohanolu.github.io/singularity/"


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def compare_archive(raw, fmt, expected):
    files = {}
    prefix = None

    def add(name, body):
        nonlocal prefix
        root, sep, path = name.partition("/")
        require(root and sep and path and path not in files, "Invalid archive entry")
        if prefix is None:
            prefix = root
        require(prefix == root and path in expected, "Unexpected archive file")
        files[path] = digest(body)

    if fmt == "zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as package:
            for item in package.infolist():
                if not item.is_dir():
                    require(item.external_attr >> 28 in (0, 8), "Nonregular ZIP entry")
                    add(item.filename, package.read(item))
    else:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as package:
            for item in package:
                if not item.isdir():
                    require(item.isfile(), "Nonregular TAR entry")
                    add(item.name, package.extractfile(item).read())
    require(files == expected, f"GitHub {fmt} differs from public files")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("--github-archives", action="store_true")
    cli.add_argument("--stage", type=Path)
    cli.add_argument("--live", action="store_true")
    args = cli.parse_args()
    manifest = json.loads(Path("distribution.json").read_text())
    request = json.loads(Path("deployment-request.json").read_text())
    require(request == {"source_sha": manifest["source_sha"]} and re.fullmatch("[a-f0-9]{40}", manifest["source_sha"]), "Invalid source binding")
    expected = manifest["files"]
    reviewed_paths = json.loads(Path(".github/scripts/singularity-public-files.json").read_text())
    require(isinstance(expected, dict) and reviewed_paths == sorted(expected)
            and {"index.html", "release.json", ".nojekyll"} <= expected.keys(),
            "Runtime differs from independently reviewed public allowlist")
    controls = {"distribution.json","deployment-request.json","README.md",".gitattributes",".github/workflows/deploy.yml",".github/scripts/verify-public-bundle.py",".github/scripts/singularity-public-files.json"}
    tracked = set(subprocess.check_output(["git","ls-files","-z"]).decode().rstrip("\0").split("\0"))
    require(tracked == expected.keys() | controls, "Unexpected file in public repository")
    if args.stage:
        args.stage.mkdir(parents=True, exist_ok=False)
    for name, checksum in expected.items():
        require(name == ".nojekyll" or re.fullmatch(r"(?:[a-zA-Z0-9-]+\.(?:css|js|html)|release\.json|assets/singularity/[a-zA-Z0-9-]+\.(?:webp|png))", name), "Invalid public path")
        p = Path(name)
        require(not p.is_symlink() and p.is_file() and digest(p.read_bytes()) == checksum, "File mismatch: " + name)
        if args.stage:
            target = args.stage / p
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, target)
    if args.github_archives:
        require(os.environ.get("GITHUB_REPOSITORY") == PUBLIC_REPO, "Unexpected repository")
        sha = subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()
        require(sha == os.environ.get("GITHUB_SHA"), "Unexpected deployment commit")
        for fmt in ("zip", "tar.gz"):
            url = f"https://codeload.github.com/{PUBLIC_REPO}/{fmt}/{sha}"
            with urllib.request.urlopen(url,timeout=45) as response:
                compare_archive(response.read(), fmt, expected)
    if args.live:
        for attempt in range(10):
            try:
                for name, checksum in expected.items():
                    url = BASE_URL + ("" if name == "index.html" else name)
                    for suffix in ("", "?stable-check=" + checksum[:16]):
                        with urllib.request.urlopen(url+suffix,timeout=15) as response:
                            require(digest(response.read()) == checksum, "Live mismatch: " + name)
                break
            except (ValueError, OSError):
                if attempt == 9:
                    raise
                time.sleep(10)
    print(f"Verified {len(expected)} public files for {manifest['source_sha']}")


if __name__ == "__main__":
    main()
