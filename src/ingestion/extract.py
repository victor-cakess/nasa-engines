import urllib.request
import zipfile
import os
from pathlib import Path

ZIP_URL = "https://data.nasa.gov/docs/legacy/CMAPSSData.zip"
DATA_DIR = Path(__file__).parent.parent / "data"
ZIP_PATH = DATA_DIR / "CMAPSSData.zip"
SENTINEL = DATA_DIR / "train_FD001.txt"


def download(url: str, dest: Path) -> None:
    print(f"Downloading {url} ...")

    def _progress(count, block_size, total_size):
        if total_size > 0:
            pct = count * block_size * 100 // total_size
            print(f"\r  {min(pct, 100)}%", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=_progress)
    print()


def extract(zip_path: Path, dest: Path) -> None:
    print(f"Extracting to {dest} ...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if SENTINEL.exists():
        print("Data already present, skipping download.")
        return

    download(ZIP_URL, ZIP_PATH)
    extract(ZIP_PATH, DATA_DIR)
    ZIP_PATH.unlink()
    print("Done.")


if __name__ == "__main__":
    main()
