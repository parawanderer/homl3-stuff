import pandas as pd
import tarfile
import urllib.request
from pathlib import Path
import os


DIRNAME = os.path.abspath(os.path.dirname(__file__))
DATASETS_DIR = "datasets"
DEFAULT_PATH = os.path.abspath(os.path.join(DIRNAME, "..", DATASETS_DIR))

class CSVLoader:
    def __init__(self, root_path: str = DEFAULT_PATH):
        self._root_path: str = root_path

    def load(self, archive_name: str, zip_url: str, output_folder: str, csv_file_path: str) -> pd.DataFrame:
        tarball_path = Path(self._root_path, archive_name)

        if not tarball_path.is_file():

            Path(self._root_path).mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(zip_url, tarball_path)

        with tarfile.open(tarball_path) as housing_tarball:
            housing_tarball.extractall(path=Path(self._root_path, output_folder))

        return pd.read_csv(Path(self._root_path, output_folder, csv_file_path))
