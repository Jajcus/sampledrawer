
import pytest

from jajcus.sample_drawer.file_analyzer import FileKey, FileAnalyzer


class TestFileKey:
    def test_as_string(self):
        key = FileKey("/some/path")
        assert key.path == "/some/path"
        assert str(key) == "/some/path"

    def test_missing(self, tmp_path):
        missing_path = tmp_path / "missing"
        key = FileKey(str(missing_path))
        assert key.path == str(missing_path)
        assert key.stat is None
        assert str(key) == str(missing_path)
        key2 = FileKey(str(missing_path))
        assert hash(key) == hash(key2)
        assert key != key2  # cannot compare files that do not exist

    def test_missing_path_object(self, tmp_path):
        missing_path = tmp_path / "missing"
        key = FileKey(missing_path)
        assert key.path == str(missing_path)
        assert key.stat is None
        assert str(key) == str(missing_path)
        key2 = FileKey(str(missing_path))
        assert hash(key) == hash(key2)
        assert key != key2  # cannot compare files that do not exist

    def test_existing_two_files(self, tmp_path):
        path1 = tmp_path / "file1"
        path2 = tmp_path / "file2"
        path1.write_text("data")
        path2.write_text("data")

        key1 = FileKey(str(path1))
        hash(key1)
        key2 = FileKey(str(path2))
        hash(key2)

        assert key1.path == str(path1)
        assert key1.stat is not None
        assert str(key1) == str(path1)

        assert key2.path == str(path2)
        assert key2.stat is not None
        assert str(key2) == str(path2)

        # different paths are always considered different files
        assert hash(key1) != hash(key2)
        assert key1 != key2

    def test_same_file(self, tmp_path):
        path = tmp_path / "file"
        path.write_text("data")
        key1 = FileKey(str(path))
        hash(key1)
        key2 = FileKey(str(path))
        hash(key2)

        assert key1.path == str(path)
        assert key1.stat is not None
        assert str(key1) == str(path)

        assert key2.path == str(path)
        assert key2.stat is not None
        assert str(key2) == str(path)

        assert hash(key1) == hash(key2)
        assert key1 == key2

    def test_modified_file(self, tmp_path):
        path = tmp_path / "file"
        path.write_text("data")
        key1 = FileKey(str(path))
        hash(key1)

        path.write_text("other data")
        key2 = FileKey(str(path))
        hash(key2)

        assert key1.path == str(path)
        assert key1.stat is not None
        assert str(key1) == str(path)

        assert key2.path == str(path)
        assert key2.stat is not None
        assert str(key2) == str(path)

        # file has been changed, it is not the same file any more
        assert hash(key1) != hash(key2)
        assert key1 != key2

    def test_path_normalization(self, tmp_path):
        path1 = tmp_path / "file"
        path1.write_text("data")
        dir_path = tmp_path / "dir"
        dir_path.mkdir()
        path2 = dir_path / ".." / "file"

        key1 = FileKey(str(path1))
        hash(key1)
        key2 = FileKey(str(path2))
        hash(key2)

        assert key1.path == str(path1.resolve())
        assert key1.stat is not None
        assert str(key1) == str(path1.resolve())

        assert key2.path == str(path1.resolve())
        assert key2.stat is not None
        assert str(key2) == str(path1.resolve())

        assert hash(key1) == hash(key2)
        assert key1 == key2


@pytest.fixture
def file_analyzer():
    return FileAnalyzer()


class TestFileAnalyzer:
    def test_get_file_info_missing(self, file_analyzer, tmp_path):
        missing_path = tmp_path / "missing"
        with pytest.raises(FileNotFoundError):
            file_analyzer.get_file_info(missing_path)

    def test_get_file_metadata_missing(self, file_analyzer, tmp_path):
        missing_path = tmp_path / "missing"
        with pytest.raises(FileNotFoundError):
            file_analyzer.get_file_metadata(missing_path)

    def test_get_file_info_silence(self, file_analyzer, shared_datadir, mocker):
        mocker.patch("jajcus.sample_drawer.file_analyzer.compute_waveform",
                     return_value="WAVEFORM")
        path = shared_datadir / "silence-1s.wav"
        file_info = file_analyzer.get_file_info(path)
        assert isinstance(file_info, dict)
        assert file_info['path'] == str(path)
        assert file_info['sample_rate'] == 44100
        assert file_info['duration'] == pytest.approx(1.0)
        assert file_info['channels'] == 1
        assert file_info['format'] == 'WAV'
        assert file_info['format_subtype'] == 'PCM_16'
        assert file_info['peak_level'] < -70.0
        assert file_info['waveform'] == "WAVEFORM"
        assert file_info['md5'] == "a39504034bb59d9b4016ad35faccc586"
