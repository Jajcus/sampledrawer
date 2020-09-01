
import os
import shutil

from unittest.mock import Mock

import pytest

from jajcus.sample_drawer.library import Library


@pytest.fixture
def library_factory(request, tmp_path_factory, shared_datadir):
    marker = request.node.get_closest_marker("library_template")
    if marker is None:
        base_path = tmp_path_factory.mktemp("lib", True)
    else:
        base_path = shared_datadir / marker.args[0]

    def _library_factory():
        return Library(Mock(), base_path=base_path)

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

    library_factory()


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


@pytest.mark.library_template("testdb_ver_0")
def test_open_existing(library_factory):
    library_factory()
