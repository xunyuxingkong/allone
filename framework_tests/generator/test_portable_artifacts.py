import errno
import json
import zipfile

import pytest

from xgtest.generator.artifact_store import ArtifactStore, LocalArtifactStore, export_artifact_bundle, import_artifact_bundle


def test_store_falls_back_when_hardlinks_unsupported(tmp_path, monkeypatch):
    store = LocalArtifactStore(tmp_path / "store")
    monkeypatch.setattr("xgtest.generator.artifact_store.os.link", lambda *a: (_ for _ in ()).throw(OSError(errno.EOPNOTSUPP, "synthetic filesystem")))
    reference = store.put(b'{"rows": [[null, 1]]}\n')
    assert isinstance(store, ArtifactStore)
    assert store.get(reference) == b'{"rows": [[null, 1]]}\n'
    assert store.put(store.get(reference)) == reference
    assert store.exists(reference)
    (store.root / reference.uri).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="ARTIFACT_HASH_MISMATCH"):
        store.put(b'{"rows": [[null, 1]]}\n')


def test_complete_bundle_roundtrip_and_corruption_is_rejected_before_import(tmp_path):
    original = LocalArtifactStore(tmp_path / "original")
    refs = (original.put(b'{"rows": [[1]]}'), original.put(b'{"rows": [[2]]}'))
    bundle = tmp_path / "evidence.zip"
    export_artifact_bundle(original, refs, bundle)
    destination = LocalArtifactStore(tmp_path / "imported")
    imported = import_artifact_bundle(destination, bundle)
    assert [destination.get(ref) for ref in imported] == [original.get(ref) for ref in refs]
    bad = tmp_path / "corrupt.zip"
    with zipfile.ZipFile(bundle) as source, zipfile.ZipFile(bad, "w") as target:
        for name in source.namelist():
            target.writestr(name, b"tampered" if name == f"objects/{refs[1].sha256}" else source.read(name))
    empty = LocalArtifactStore(tmp_path / "empty")
    with pytest.raises(ValueError, match="ARTIFACT_BUNDLE_HASH_MISMATCH"):
        import_artifact_bundle(empty, bad)
    assert not empty.root.exists()


def test_bundle_limits_and_unexpected_entries_are_rejected(tmp_path):
    store = LocalArtifactStore(tmp_path / "store")
    ref = store.put(b"complete original bytes")
    bundle = tmp_path / "bundle.zip"
    export_artifact_bundle(store, (ref,), bundle)
    with pytest.raises(ValueError, match="BUNDLE_LIMIT"):
        import_artifact_bundle(store, bundle, max_bytes=1)
    with zipfile.ZipFile(bundle, "a") as archive:
        archive.writestr("../outside", "never extract")
    with pytest.raises(ValueError, match="BUNDLE_SCOPE"):
        import_artifact_bundle(store, bundle)
