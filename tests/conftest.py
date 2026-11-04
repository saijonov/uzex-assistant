import zipfile
from pathlib import Path

import pytest

from uzex.database import Database
from uzex.ingest import import_archive


@pytest.fixture(scope="session")
def sample_database(tmp_path_factory):
    directory = tmp_path_factory.mktemp("registry")
    archive = directory / "sample.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        for path in Path("tests/fixtures").glob("*.csv"):
            zipped.write(path, f"uzex_spot_data/{path.name}")
    destination = directory / "registry.duckdb"
    import_archive(archive, destination)
    return Database(destination)
