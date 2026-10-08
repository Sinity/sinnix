"""An explicit publication projection must not expose private directories."""

from pathlib import Path
import runpy

import pytest

BUILD = runpy.run_path(str(Path(__file__).parents[3] / "scripts/sinnix-report-site"))["build"]


def test_only_selected_files_are_published_with_stable_relative_urls(tmp_path):
    subject = tmp_path / "subject"
    subject.mkdir()
    report = subject / "report.html"
    report.write_text("<p>report</p>")
    (subject / "unpublished.txt").write_text("private")
    output = tmp_path / "site"
    BUILD({"schema_version": 1, "files": [{"url": "existing/report.html", "source": str(report)}]}, output)
    link = output / "existing/report.html"
    assert link.is_symlink() and link.read_text() == "<p>report</p>"
    assert not (output / "existing/unpublished.txt").exists()
    (subject / "added-later.txt").write_text("also private")
    assert not (output / "existing/added-later.txt").exists()


@pytest.mark.parametrize("url", ["../escape", "/absolute", "a/../escape", "a//b", ".hidden", "a\\b"])
def test_unsafe_urls_refuse_before_creating_any_site(tmp_path, url):
    source = tmp_path / "report.html"
    source.touch()
    output = tmp_path / "site"
    with pytest.raises(ValueError):
        BUILD({"schema_version": 1, "files": [{"url": url, "source": str(source)}]}, output)
    assert not output.exists()


def test_private_input_and_directory_publication_are_refused(tmp_path):
    private = tmp_path / "catalog"
    private.mkdir()
    source = private / "catalog.json"
    source.write_text("{}")
    for file in [source, private]:
        with pytest.raises(ValueError):
            BUILD({"schema_version": 1, "private_roots": [str(private)],
                   "files": [{"url": "data", "source": str(file)}]}, tmp_path / "site")
    assert not (tmp_path / "site").exists()


def test_companions_and_translations_keep_their_urls_but_conflicts_are_refused(tmp_path):
    source = tmp_path / "source"
    source.write_text("data")
    output = tmp_path / "site"
    BUILD({"schema_version": 1, "files": [{"url": url, "source": str(source)}
        for url in ["report.html", "report.pl.html", "assets/data.json"]]}, output)
    assert sorted(p.relative_to(output).as_posix() for p in output.rglob("*") if p.is_file()) == [
        "assets/data.json", "report.html", "report.pl.html"]
    for urls in [["a", "a"], ["a", "a/b"]]:
        with pytest.raises(ValueError):
            BUILD({"schema_version": 1, "files": [{"url": url, "source": str(source)} for url in urls]}, tmp_path / "conflict")
    assert not (tmp_path / "conflict").exists()
