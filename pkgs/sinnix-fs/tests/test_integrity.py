"""Synthetic counterexamples for digest identity and taxonomy inheritance.

These use the real DuckDB CLI over tiny isolated fixtures, never the host index.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / 'scripts' / 'sinnix-fs'


def load(host_policy=False):
    module = SourceFileLoader('filesystem_integrity_under_test', str(SCRIPT)).load_module()
    if not host_policy:
        module.CONTENT_COLLECTION_BOUNDARIES = {}
    return module


def sql(db, query):
    assert shutil.which('duckdb'), 'DuckDB is required for the owner integration tests'
    proc = subprocess.run(['duckdb',str(db),'-json','-c',query],capture_output=True,text=True,timeout=15)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout) if proc.stdout.strip() else []


def row(path, size=4, digest=None, **extra):
    return {'schema':'sinnix-fs-content-v1','path':path,'dir':str(Path(path).parent),
            'name':Path(path).name,'ext':'.md','bytes':size,'mtime':0,
            'sha256':digest or hashlib.sha256(b'test').hexdigest(),
            'title':None,'head':None,'magic_type':None,'line_count':None,'error':None,**extra}


def materialize(fs, root, rows):
    source=root/'files.jsonl';source.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    fs.content_materialize(source,root/'content.duckdb',root/'files.parquet')
    return root/'content.duckdb'


def test_full_digest_is_hash_of_all_bytes_and_empty_files_are_kept(tmp_path):
    fs=load();p=tmp_path/'note.md';p.write_bytes(b'hello')
    result=fs.content_fingerprint(p,p.stat().st_size)
    assert result['sha256']==hashlib.sha256(b'hello').hexdigest()
    assert result['sample_sha256'] is None and result['fingerprint_kind']=='sha256-full'
    assert result['fingerprint_bytes']==5
    p.write_bytes(b'')
    assert fs.content_walk([str(tmp_path)],tmp_path/'out.jsonl',0)==1
    result=json.loads((tmp_path/'out.jsonl').read_text())
    assert result['bytes']==0 and result['sha256']==hashlib.sha256(b'').hexdigest()


def test_same_head_tail_size_different_middle_are_not_exact_duplicates(tmp_path):
    fs=load();a=tmp_path/'a.md';b=tmp_path/'b.md'
    data=b'A'*(9<<20);a.write_bytes(data);b.write_bytes(data[:4<<20]+b'B'+data[(4<<20)+1:])
    assert hashlib.sha256(a.read_bytes()).digest()!=hashlib.sha256(b.read_bytes()).digest()
    fa=fs.content_fingerprint(a,a.stat().st_size);fb=fs.content_fingerprint(b,b.stat().st_size)
    assert fa['sample_sha256']==fb['sample_sha256']
    assert fa['sha256'] is fb['sha256'] is None
    assert fa['fingerprint_bytes']==2<<20
    rows=[row(str(p),p.stat().st_size,schema=fs.CONTENT_SCHEMA,**f) for p,f in [(a,fa),(b,fb)]]
    # row()'s compatibility default cannot replace explicit NULL digest.
    for r in rows:r['sha256']=None
    db=materialize(fs,tmp_path,rows)
    assert sql(db,'SELECT count(*) AS n FROM duplicates')[0]['n']==0
    assert sql(db,'SELECT candidates FROM sampled_duplicate_candidates')[0]['candidates']==2


def test_v1_large_digest_is_demoted_but_small_full_digests_remain(tmp_path):
    fs=load();db=materialize(fs,tmp_path,[row('/a',9<<20),row('/b',9<<20),row('/c'),row('/d')])
    assert sql(db,'SELECT copies,unit_bytes FROM duplicates')==[{'copies':2,'unit_bytes':4}]
    large=sql(db,'SELECT sha256,sample_sha256,fingerprint_kind FROM files WHERE bytes>8388608')
    assert all(x['sha256'] is None and x['sample_sha256'] and x['fingerprint_kind']=='sha256-head-tail-size-v1' for x in large)


def test_unknown_schema_and_errored_records_do_not_become_content_identity(tmp_path):
    fs=load();db=materialize(fs,tmp_path,[row('/unknown',schema='other'),row('/bad',error='read failed'),row('/ok')])
    assert sql(db,'SELECT count(sha256) AS n FROM files')==[{'n':1}]
    assert sql(db,'SELECT count(*) AS n FROM duplicates')==[{'n':0}]


def test_legacy_view_repair_changes_no_source_rows_and_is_repeatable(tmp_path):
    fs=load();db=tmp_path/'content.duckdb';digest='a'*64
    sql(db,"CREATE TABLE files(schema VARCHAR,path VARCHAR,bytes BIGINT,sha256 VARCHAR,error VARCHAR,name VARCHAR);"
           f"INSERT INTO files VALUES ('sinnix-fs-content-v1','/one',9437184,'{digest}',NULL,'one'),"
           f"('sinnix-fs-content-v1','/two',9437184,'{digest}',NULL,'two');"
           "CREATE VIEW duplicates AS SELECT sha256,count(*) AS copies FROM files GROUP BY sha256;")
    before=sql(db,'SELECT * FROM files ORDER BY path')
    assert fs.content_views_refresh(db)==0
    assert fs.content_views_refresh(db)==0
    assert sql(db,'SELECT * FROM files ORDER BY path')==before
    assert sql(db,'SELECT count(*) AS n FROM duplicates')==[{'n':0}]
    assert sql(db,'SELECT candidates FROM sampled_duplicate_candidates')==[{'candidates':2}]


def test_broken_json_never_replaces_previous_materializations(tmp_path):
    fs=load();source=tmp_path/'bad.jsonl';source.write_text('{not json}\n')
    db=tmp_path/'content.duckdb';pq=tmp_path/'files.parquet'
    db.write_bytes(b'old database');pq.write_bytes(b'old parquet')
    with pytest.raises(SystemExit):fs.content_materialize(source,db,pq)
    assert db.read_bytes()==b'old database' and pq.read_bytes()==b'old parquet'


def test_aliases_and_special_files_are_not_opened_as_payloads(tmp_path,monkeypatch):
    fs=load();p=tmp_path/'note.md';p.write_text('data');alias=tmp_path/'alias.md';alias.symlink_to(p)
    fifo=tmp_path/'fifo.md';os.mkfifo(fifo)
    original=os.open
    def guarded(path,*args,**kwargs):
        assert Path(path) not in (alias,fifo),'attempted alias or FIFO open'
        return original(path,*args,**kwargs)
    monkeypatch.setattr(fs.os,'open',guarded)
    for q in [alias,fifo]:assert fs.content_fingerprint(q,q.lstat().st_size)['sha256'] is None
    assert fs.content_walk([str(tmp_path)],tmp_path/'out.jsonl',0)==3
    rows={r['name']:r for r in map(json.loads,(tmp_path/'out.jsonl').read_text().splitlines())}
    assert rows['alias.md']['sha256'] is None and rows['fifo.md']['sha256'] is None


def test_changed_observed_version_has_no_fingerprint(tmp_path):
    fs=load();p=tmp_path/'file';p.write_bytes(b'old');before=p.stat();p.write_bytes(b'new')
    got=fs.content_fingerprint(p,3,expected=before)
    assert got['sha256'] is None and got['error']=='changed before fingerprint'


def test_missing_and_symlink_roots_are_explicit_inventory_rows(tmp_path):
    fs=load();missing=tmp_path/'missing';real=tmp_path/'real';real.mkdir();alias=tmp_path/'alias';alias.symlink_to(real)
    out=tmp_path/'nodes.jsonl';assert fs.inventory_scan([str(missing),str(alias)],-1,out,0)==2
    rows=list(map(json.loads,out.read_text().splitlines()))
    assert {r['path'] for r in rows}=={str(missing),str(alias)}
    assert all(r['error'] for r in rows)


def test_breadth_first_directory_order_is_preserved(tmp_path):
    fs=load();root=tmp_path/'root';(root/'a'/'deep').mkdir(parents=True);(root/'b').mkdir()
    out=tmp_path/'nodes.jsonl';fs.inventory_scan([str(root)],-1,out,0)
    depths=[r['depth'] for r in map(json.loads,out.read_text().splitlines())]
    assert depths==[0,1,1,2]


def test_component_prefix_and_legacy_sha_judgments_are_not_overextended(tmp_path, monkeypatch):
    # Neither a per-user extension cache nor a network install is necessary.
    home = tmp_path / "nonexistent-home"
    monkeypatch.setenv("HOME", str(home))
    assert not home.exists()
    fs=load();db=tmp_path/'inventory.duckdb';ctn=tmp_path/'content.duckdb'
    sql(db,"CREATE TABLE nodes(path VARCHAR); INSERT INTO nodes VALUES ('/foo'),('/foo/child'),('/foobar'),('/slash'),('/slash/child'),('/slashish');")
    large='a'*64
    sql(ctn,"CREATE TABLE files(schema VARCHAR,path VARCHAR,bytes BIGINT,sha256 VARCHAR,error VARCHAR);"
            f"INSERT INTO files VALUES ('sinnix-fs-content-v1','/large',9437184,'{large}',NULL);")
    judgments=[]
    for target,value in [('prefix:/foo','foo'),('prefix:/slash/','slash'),('sha256:'+large,'must-not-inherit-sample')]:
        judgments.append({'target':target,'field':'subject','value':value,'confidence':1.0,'observation':'known','method':'operator','evidence':'fixture','ts':'2026-01-01T00:00:00Z'})
    (tmp_path/'judgments.jsonl').write_text(''.join(json.dumps(j)+'\n' for j in judgments))
    assert fs.ledger_run(tmp_path)==0
    actual=sql(db,'SELECT path,value FROM inherited_judgments ORDER BY path')
    assert actual==[{'path':'/foo','value':'foo'},{'path':'/foo/child','value':'foo'},{'path':'/slash','value':'slash'},{'path':'/slash/child','value':'slash'}]


def test_missing_content_root_is_an_unavailable_row_not_an_empty_result(tmp_path):
    fs=load();out=tmp_path/'files.jsonl';root=tmp_path/'gone'
    assert fs.content_walk([str(root)],out,0)==1
    result=json.loads(out.read_text())
    assert result['path']==str(root) and result['kind']=='directory' and result['error']


def test_materialization_accepts_quoted_filesystem_paths(tmp_path):
    fs=load();root=tmp_path/"quote's directory";root.mkdir()
    db=materialize(fs,root,[row('/note')])
    assert sql(db,'SELECT count(*) AS n FROM files')==[{'n':1}]


def test_mutation_during_hash_read_discards_the_result(tmp_path,monkeypatch):
    fs=load();p=tmp_path/'mutable';p.write_bytes(b'old')
    real=hashlib.sha256
    class MutatingHash:
        def __init__(self):self.h=real()
        def update(self,data):self.h.update(data);p.write_bytes(b'new')
        def hexdigest(self):return self.h.hexdigest()
    monkeypatch.setattr(fs.hashlib,'sha256',MutatingHash)
    result=fs.content_fingerprint(p,3)
    assert result['sha256'] is None and result['error']=='changed while fingerprinting'


def test_native_collection_boundary_does_not_read_or_enumerate_its_payloads(tmp_path,monkeypatch):
    fs=load();root=tmp_path/'root';native=root/'native';native.mkdir(parents=True)
    (native/'must-not-read.md').write_text('private payload')
    (root/'ordinary.md').write_text('ordinary')
    monkeypatch.setattr(fs,'CONTENT_COLLECTION_BOUNDARIES',{str(native):'native owner'})
    real_scandir=os.scandir
    def guarded_scandir(path):
        assert isinstance(path, int) or Path(path)!=native,'native collection was enumerated'
        return real_scandir(path)
    monkeypatch.setattr(fs.os,'scandir',guarded_scandir)
    out=tmp_path/'files.jsonl';assert fs.content_walk([str(root)],out,0)==2
    rows={r['path']:r for r in map(json.loads,out.read_text().splitlines())}
    assert rows[str(native)]['kind']=='collection_boundary'
    assert rows[str(native)]['exclusion_reason']=='native owner'
    assert rows[str(native)]['sha256'] is None and rows[str(native)]['error'] is None
    assert str(native/'must-not-read.md') not in rows
    db=tmp_path/'content.duckdb';fs.content_materialize(out,db,tmp_path/'files.parquet')
    assert sql(db,"SELECT count(*) AS n FROM files WHERE kind='collection_boundary' AND exclusion_reason='native owner'")==[{'n':1}]


def test_explicitly_requested_excluded_root_is_still_visible_without_walk(tmp_path,monkeypatch):
    fs=load();root=tmp_path/'native';root.mkdir()
    monkeypatch.setattr(fs,'CONTENT_COLLECTION_BOUNDARIES',{str(root):'native owner'})
    def forbidden(*a,**k):raise AssertionError('walked explicitly excluded root')
    monkeypatch.setattr(fs.os,'walk',forbidden)
    out=tmp_path/'out.jsonl';assert fs.content_walk([str(root)],out,0)==1
    assert json.loads(out.read_text())['kind']=='collection_boundary'


def test_scan_exclusion_is_a_component_boundary_not_a_lexical_prefix():
    fs=load(host_policy=True)
    assert fs.content_excluded('/realm/state/polylogue')
    assert fs.content_excluded('/realm/state/polylogue/inside')
    assert fs.content_excluded('/realm/state/polylogue-report') is None
    assert fs.content_excluded('/realm/tmp')
    assert fs.content_excluded('/realm/tmp/work/anything')
    assert fs.content_excluded('/realm/tmp-other') is None
    assert fs.content_excluded('/realm/library/images')
    assert fs.content_excluded('/realm/library/images-extra') is None


def test_generated_directory_exclusion_keeps_a_boundary_record(tmp_path):
    fs=load();root=tmp_path/'root';cache=root/'node_modules';cache.mkdir(parents=True)
    (cache/'package.json').write_text('{}')
    out=tmp_path/'out.jsonl';fs.content_walk([str(root)],out,0)
    rows=list(map(json.loads,out.read_text().splitlines()))
    assert len(rows)==1 and rows[0]['kind']=='collection_boundary'
    assert rows[0]['exclusion_reason']=='inside node_modules'
