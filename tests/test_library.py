
import os
import shutil
import sqlite3

from unittest.mock import Mock

import pytest

from jajcus.sample_drawer.library import Library, LibraryError
from jajcus.sample_drawer.search import SearchQuery


@pytest.fixture
def library_factory(request, tmp_path_factory, shared_datadir):
    marker = request.node.get_closest_marker("library_template")
    if marker is None:
        base_path = tmp_path_factory.mktemp("lib", True)
    else:
        base_path = shared_datadir / marker.args[0] / "library"

    def _library_factory():
        return Library(Mock(name="appdirs Mock"), base_path=base_path)

    _library_factory.base_path = base_path
    yield _library_factory

    if base_path.exists():
        shutil.rmtree(base_path)


def test_create_new(library_factory):
    library = library_factory()
    base_path = library_factory.base_path
    assert (base_path / "database.db").exists()

    del library
    assert (base_path / "database.db").exists()

    library = library_factory()
    tags = list(library.get_tags())
    assert tags == [("/", 0)]


def test_create_premissions_error(library_factory):
    base_path = library_factory.base_path
    base_path.chmod(0o000)
    try:
        with pytest.raises(LibraryError, match="Cannot open database"):
            library_factory()
    finally:
        base_path.chmod(0o700)


def test_tmp_dir_del(library_factory):
    library = library_factory()
    base_path = library_factory.base_path
    lib_tmp_dir = library.tmp_dir
    assert os.path.exists(lib_tmp_dir)
    assert str(base_path / os.path.basename(lib_tmp_dir)) == lib_tmp_dir
    del library
    assert not os.path.exists(lib_tmp_dir)


def test_tmp_dir_close(library_factory):
    library = library_factory()
    base_path = library_factory.base_path
    lib_tmp_dir = library.tmp_dir
    assert os.path.exists(lib_tmp_dir)
    assert str(base_path / os.path.basename(lib_tmp_dir)) == lib_tmp_dir
    library.close()
    assert not os.path.exists(lib_tmp_dir)


def test_open_existing_unknown_db(library_factory):
    base_path = library_factory.base_path
    db = sqlite3.connect(base_path / "database.db")
    db.execute("CREATE TABLE test (id PRIMARY KEY)")
    db.commit()
    db.close()
    with pytest.raises(LibraryError, match="Cannot open database"):
        library_factory()


def test_open_existing_invalid_db(library_factory):
    library = library_factory()
    base_path = library_factory.base_path
    library.close()
    db = sqlite3.connect(base_path / "database.db")
    db.execute("DELETE FROM db_meta")
    db.commit()
    db.close()
    with pytest.raises(LibraryError, match="Invalid database"):
        library = library_factory()


def test_open_existing_bad_version(library_factory):
    library = library_factory()
    base_path = library_factory.base_path
    library.close()
    db = sqlite3.connect(base_path / "database.db")
    db.execute("UPDATE db_meta SET version='XX'")
    db.commit()
    db.close()
    with pytest.raises(LibraryError, match="Unsupported database version: 'XX'"):
        library = library_factory()


@pytest.mark.library_template("testdb_ver_0")
def test_open_existing_testdb_ver_0(library_factory):
    library = library_factory()
    tags = list(library.get_tags())
    tags.sort()
    assert tags == [("/", 3), ("tag1", 2), ("tag2", 1)]
    items = library.get_items(SearchQuery([]))
    assert len(items) == 3
    names = {item.name for item in items}
    assert names == {"silence-1s", "sine-440Hz-half_scale-1s"}
    formats = {item.format for item in items}
    assert formats == {"FLAC", "WAV"}

    query = SearchQuery.from_string("_name=silence-1s _format=WAV")
    item = library.get_items(query)[0]
    assert item.name == "silence-1s"
    assert item.format == "WAV"
    path = library.get_library_object_path(item)
    assert os.path.isfile(path)

    query = SearchQuery.from_string("_name=sine-440Hz-half_scale-1s _format=FLAC")
    item = library.get_items(query)[0]
    assert item.name == "sine-440Hz-half_scale-1s"
    assert item.format == "FLAC"
    path = library.get_library_object_path(item)
    assert path != item.path  # item in the library
    assert path.startswith(str(library_factory.base_path))
    assert os.path.isfile(path)

    query = SearchQuery.from_string("_name=sine-440Hz-half_scale-1s _format=WAV")
    item = library.get_items(query)[0]
    assert item.name == "sine-440Hz-half_scale-1s"
    assert item.format == "WAV"
    path = library.get_library_object_path(item)
    assert path == item.path  # external item
    assert not path.startswith(str(library_factory.base_path))
