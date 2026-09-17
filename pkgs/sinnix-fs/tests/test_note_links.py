"""Synthetic tests for conservative note-link planning and pure rewrites."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import pytest

MODULE = Path(importlib.util.find_spec('sinnix_lib.note_links').origin)

def load():
    spec=importlib.util.spec_from_file_location('note_links_under_test',MODULE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def note(root,name,text):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode());return p

def scan(root,**kwargs):return load().scan_notes([root],**kwargs)

def test_id_and_explicit_alias_resolve_and_originals_remain_unchanged(tmp_path):
    source=note(tmp_path,'one.md','[[stable.two]] and [[Other title]]')
    target=note(tmp_path,'renamed.md','---\nid: stable.two\naliases:\n  - Other title\n---\n# Body')
    before={p:p.read_bytes() for p in [source,target]};p=scan(tmp_path)
    assert p['complete'] and p['counts']['proposed_edits']==2
    fixed=load().rewrite(source.read_text(),p['changes'][0]['edits'])
    assert fixed=='[stable.two](renamed.md) and [Other title](renamed.md)'
    assert all(path.read_bytes()==data for path,data in before.items())

def test_equal_name_candidates_are_ambiguous(tmp_path):
    note(tmp_path,'source.md','[[target]]');note(tmp_path,'a/target.md','first');note(tmp_path,'b/target.md','second')
    p=scan(tmp_path);assert p['references'][0]['status']=='ambiguous' and not p['changes']

def test_duplicate_stable_ids_do_not_choose_a_copy(tmp_path):
    for name in ['a.md','b.md']:note(tmp_path,name,'---\nid: same.id\n---\n')
    note(tmp_path,'source.md','[[same.id]]');p=scan(tmp_path)
    assert p['references'][0]['status']=='ambiguous' and not p['changes']

def test_primary_id_precedes_historical_copy_without_editing_reference_roots(tmp_path):
    root=tmp_path/'current';ref=tmp_path/'history'
    note(root,'target.md','---\nid: same.id\n---\n');note(ref,'target.md','---\nid: same.id\n---\n[[same.id]]')
    note(root,'source.md','[[same.id]]');p=load().scan_notes([root],[ref])
    assert p['counts']['references']==1 and p['changes'][0]['edits'][0]['destination']==str(root/'target.md')

def test_reference_only_target_is_linked_but_never_rewritten(tmp_path):
    root=tmp_path/'current';ref=tmp_path/'history'
    note(root,'source.md','[[historic.id]]');note(ref,'old.md','---\nid: historic.id\n---\n[[missing]]')
    p=load().scan_notes([root],[ref]);assert p['counts']['proposed_edits']==1
    assert p['changes'][0]['edits'][0]['after']=='[historic.id](../history/old.md)'

def test_no_basename_guess_for_retired_qualified_path(tmp_path):
    note(tmp_path,'source.md','[[old/path/target]]');note(tmp_path,'target.md','hello')
    p=scan(tmp_path);assert p['references'][0]['status']=='unresolved'

def test_exact_relative_scoped_path_is_supported(tmp_path):
    note(tmp_path,'source.md','[[sub/target]]');note(tmp_path,'sub/target.md','hello')
    assert scan(tmp_path)['changes'][0]['edits'][0]['after']=='[sub/target](sub/target.md)'

def test_unindexed_absolute_path_is_not_read(tmp_path,monkeypatch):
    note(tmp_path,'source.md','[[/not/in/scope.md]]');p=scan(tmp_path)
    assert p['references'][0]['status']=='unresolved' and p['counts']['documents']==1

def test_embeds_code_comments_frontmatter_and_escapes_are_not_links(tmp_path):
    text='---\nid: source\nsummary: "[[target]]"\n---\n'
    text+='![[target]] `[[target]]` \\[[target]]\n<!-- [[target]] -->\n'
    text+='```md\n[[target]]\n```\n~~~\n[[target]]\n~~~\n    [[target]]\n'
    text+='[[target]]\n'
    note(tmp_path,'source.md',text);note(tmp_path,'target.md','body');p=scan(tmp_path)
    assert p['counts']['references']==1 and p['counts']['proposed_edits']==1
    fixed=load().rewrite(text,p['changes'][0]['edits']);assert fixed==text[:-11]+'[target](target.md)\n'

@pytest.mark.parametrize('token',['target|label','label|target','target#heading'])
def test_unknown_wikilink_dialects_and_anchors_are_explicit(tmp_path,token):
    note(tmp_path,'source.md','[['+token+']]');note(tmp_path,'target.md','body')
    p=scan(tmp_path);assert p['references'][0]['status']=='unsupported-syntax' and not p['changes']

def test_path_quoting_and_unicode_offsets_preserve_crlf(tmp_path):
    src=note(tmp_path,'source.md','żółć\r\n[[stable]]\r\n');note(tmp_path,'a # (b).md','---\nid: stable\n---\n')
    p=scan(tmp_path);fixed=load().rewrite(src.read_bytes().decode(),p['changes'][0]['edits'])
    assert fixed=='żółć\r\n[stable](a%20%23%20%28b%29.md)\r\n'

def test_reference_to_self_is_not_rewritten(tmp_path):
    note(tmp_path,'a.md','[[a]]');p=scan(tmp_path)
    assert p['references'][0]['status']=='self-reference' and not p['changes']

def test_symlink_and_native_git_boundaries_are_not_traversed(tmp_path):
    note(tmp_path,'source.md','[[secret]]');native=tmp_path/'repo';(native/'.git').mkdir(parents=True)
    note(native,'secret.md','---\nid: secret\n---\n');(tmp_path/'alias.md').symlink_to(native/'secret.md')
    p=scan(tmp_path);assert p['complete'] and p['counts']['documents']==1
    assert p['references'][0]['status']=='unresolved' and len(p['boundaries'])==2

def test_missing_root_disables_edits_in_partial_scope(tmp_path):
    note(tmp_path,'source.md','[[target]]');note(tmp_path,'target.md','body')
    p=load().scan_notes([tmp_path,tmp_path/'missing'])
    assert not p['complete'] and not p['changes']

def test_read_budget_does_not_emit_an_applicable_partial_plan(tmp_path):
    note(tmp_path,'source.md','[[target]]');note(tmp_path,'target.md','body'*100)
    try:p=scan(tmp_path,max_bytes=20)
    except ValueError:return
    assert not p['complete'] and not p['changes']

def test_duplicate_frontmatter_id_is_not_guessed(tmp_path):
    note(tmp_path,'source.md','[[target]]');note(tmp_path,'target.md','---\nid: first\nid: second\n---\n')
    p=scan(tmp_path);assert not p['complete'] and not p['changes']

def test_pure_rewrite_rejects_stale_or_overlapping_edits():
    m=load();e={'start':0,'end':3,'before':'old','after':'new'}
    with pytest.raises(ValueError):m.rewrite('different',[e])
    with pytest.raises(ValueError):m.rewrite('old',[e,e])

def test_marker_bytes_and_payload_digest_are_separate(tmp_path):
    p=note(tmp_path,'file.md','abc');text,facts=load().read_note(p,100)
    assert text=='abc' and len(facts['sha256'])==64 and facts['bytes']==3

def test_metadata_supports_simple_quoted_aliases():
    ids,aliases,_=load().note_metadata('---\nid: "permanent.id"\naliases:\n  - \'A title\'\n---\n')
    assert ids==['permanent.id'] and aliases==['A title']

def test_changed_object_is_rejected_before_payload_read(tmp_path,monkeypatch):
    m=load();p=note(tmp_path,'file.md','old');original=os.open
    def race(path,*args,**kwargs):
        p.write_text('longer');return original(path,*args,**kwargs)
    monkeypatch.setattr(m.os,'open',race)
    with pytest.raises(ValueError,match='changed'):m.read_note(p,100)


def test_plain_flow_aliases_and_quoted_commas():
    _,aliases,_=load().note_metadata("---\nid: a\naliases: [Plain title, 'Comma, title', \"Double quoted\"]\n---\n")
    assert aliases==['Plain title','Comma, title','Double quoted']


def test_plain_alias_may_contain_internal_ampersand():
    ids,aliases,_=load().note_metadata("---\nid: career\naliases:\n  - Career & Education\n---\n")
    assert ids==['career'] and aliases==['Career & Education']

@pytest.mark.parametrize('alias',['&anchor','*alias','!tag value'])
def test_yaml_evaluation_markers_are_not_identity_strings(alias):
    with pytest.raises(ValueError):load().note_metadata('---\nid: a\naliases:\n  - '+alias+'\n---\n')


def test_cli_returns_a_plan_without_modifying_notes(tmp_path):
    import subprocess, sys
    source=note(tmp_path,'one.md','[[two]]');note(tmp_path,'two.md','body')
    script=Path(__file__).parents[3]/'scripts'/'sinnix-fs'
    run=subprocess.run([sys.executable,str(script),'note-links','--root',str(tmp_path)],capture_output=True,text=True,timeout=10)
    assert run.returncode==1,run.stderr
    plan=json.loads(run.stdout)
    assert plan['complete'] and plan['counts']['proposed_edits']==1
    assert source.read_text()=='[[two]]'


def test_cli_missing_scope_fails_without_edit_proposals(tmp_path):
    import subprocess, sys
    script=Path(__file__).parents[3]/'scripts'/'sinnix-fs'
    run=subprocess.run([sys.executable,str(script),'note-links','--root',str(tmp_path/'absent')],capture_output=True,text=True,timeout=10)
    assert run.returncode==2,run.stderr
    plan=json.loads(run.stdout)
    assert not plan['complete'] and not plan['changes']
