"""Native Git repair preserves refs and publishes receipts at caller paths."""
import json
from pathlib import Path
import subprocess
import sys
import pytest

SCRIPT=Path(__file__).resolve().parents[3]/"scripts"/"sinnix-git-store-repair"

def git(path,*args):
    return subprocess.check_output(["git","-C",str(path),*args],text=True).strip()

def borrowed_store(root):
    owner=root/"owner"
    subprocess.run(["git","init","--quiet","--initial-branch=main",str(owner)],check=True)
    git(owner,"config","user.name","Fixture")
    git(owner,"config","user.email","fixture@example.invalid")
    (owner/"neutral.txt").write_text("retained neutral evidence\n")
    git(owner,"add","neutral.txt");git(owner,"commit","--quiet","-m","neutral fixture")
    store=root/"borrowed"
    subprocess.run(["git","clone","--quiet","--bare","--shared",str(owner),str(store)],check=True)
    return owner,store

@pytest.mark.parametrize("relative_destination,relative_receipt",[(True,True),(False,True),(True,False)])
def test_caller_relative_paths_produce_independent_store_and_local_receipt(tmp_path,relative_destination,relative_receipt):
    owner,store=borrowed_store(tmp_path)
    refs=git(store,"show-ref");head=(store/"HEAD").read_bytes()
    alternates=(store/"objects/info/alternates").read_bytes()
    destination=tmp_path/"archive"/"store";receipt=tmp_path/"receipts"/"store"
    result=subprocess.run([sys.executable,str(SCRIPT),"borrowed","owner/.git/objects",
                          str(destination.relative_to(tmp_path) if relative_destination else destination),
                          str(receipt.relative_to(tmp_path) if relative_receipt else receipt)],
                         cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    published=json.loads(result.stdout)
    assert published["destination"]==str(destination)
    assert published["bundle"]==str(receipt/"reachable.bundle")
    assert (receipt/"alternates.before").read_bytes()==alternates
    assert (receipt/"HEAD.before").read_bytes()==head
    assert (receipt/"reachable.bundle").is_file()
    assert not store.exists() and not (destination/"objects/info/alternates").exists()
    owner.rename(tmp_path/"owner-offline")
    assert git(destination,"show-ref")==refs
    assert (destination/"HEAD").read_bytes()==head
    git(destination,"fsck","--full")
    git(destination,"bundle","verify",str(receipt/"reachable.bundle"))

@pytest.mark.parametrize("occupied", ["receipt", "destination"])
@pytest.mark.parametrize("dangling", [False, True])
def test_existing_output_refuses_without_changing_borrowed_store(tmp_path, occupied, dangling):
    owner,store=borrowed_store(tmp_path)
    original=(store/"objects/info/alternates").read_bytes()
    receipt=tmp_path/"receipt"
    placeholder=tmp_path/occupied
    if dangling:
        placeholder.symlink_to(tmp_path/"missing")
    else:
        placeholder.mkdir()
    result=subprocess.run([sys.executable,str(SCRIPT),str(store),str(owner/".git/objects"),str(tmp_path/"destination"),str(receipt)],capture_output=True,text=True)
    assert result.returncode!=0
    assert (store/"objects/info/alternates").read_bytes()==original
    if occupied == "receipt":
        assert not (tmp_path/"destination").exists()
    else:
        assert not receipt.exists()
