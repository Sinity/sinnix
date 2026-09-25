"""Read-only classifications from the existing ledger, not a second store."""
from __future__ import annotations
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

SCRIPT=Path(__file__).parents[3]/'scripts'/'sinnix-fs'

def load():
    loader=SourceFileLoader('judgment_tests',str(SCRIPT))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    module=importlib.util.module_from_spec(spec);loader.exec_module(module)
    return module

def decision(target='/a',field='topic',value='alpha',method='rule',ts='2026-01-01T00:00:00Z',**extra):
    return {'target':'prefix:'+target,'field':field,'value':value,'method':method,'ts':ts,'evidence':'synthetic fixture',**extra}

def ledger(fs,tmp_path,rows):
    path=tmp_path/'judgments.jsonl';path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return fs.read_judgments(path)

def test_operator_precedence_and_path_specificity(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(method='operator'),decision(value='later model',ts='2026-02-01T00:00:00Z'),decision('/a/b',value='specific')])
    assert fs.resolve_judgments(ls,'/a')['topic']['value']=='alpha'
    assert fs.resolve_judgments(ls,'/a/b/c')['topic']['value']=='specific'
    assert fs.resolve_judgments(ls,'/ab')=={}

def test_field_inheritance_keeps_distinct_owners_and_subjects(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(field='maintenance_owner',value='owner'),decision('/a/b',value='topic')])
    fields=fs.resolve_judgments(ls,'/a/b')
    assert fields['topic']['via']=='/a/b' and fields['maintenance_owner']['via']=='/a'

def test_unknown_specific_rule_blocks_general_known_value(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(),decision('/a/b',value='mixed',observation='unknown')])
    assert fs.resolve_judgments(ls,'/a/b/c')['topic']['status']=='unknown'

def test_equal_rank_disagreement_is_reported_not_ordered_away(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(),decision(value='beta')]);got=fs.resolve_judgments(ls,'/a')['topic']
    assert got['status']=='ambiguous' and 'value' not in got
    assert len(got['evidence'])==2

def test_duplicate_equal_decisions_retain_both_evidence_rows(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(),decision()]);got=fs.resolve_judgments(ls,'/a')['topic']
    assert got['status']=='known' and len(got['evidence'])==2

def test_decision_times_use_offsets_not_string_order(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(value='earlier',ts='2026-01-01T01:00:00+02:00'),decision(value='later',ts='2026-01-01T00:00:00Z')])
    assert fs.resolve_judgments(ls,'/a')['topic']['value']=='later'

def test_root_and_trailing_slash_are_component_aware(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision('/',field='role',value='root'),decision('/a/')])
    assert fs.resolve_judgments(ls,'/a/child')['topic']['value']=='alpha'
    assert set(fs.resolve_judgments(ls,'/another'))=={'role'}

@pytest.mark.parametrize('path',['relative','//a','/a/../b','/a//b','/a/./b','/a\n'])
def test_ambiguous_path_spellings_are_rejected(path):
    with pytest.raises(ValueError):load().judgment_target('prefix:'+path)

def test_filename_shaped_digest_is_rejected_and_preserved_on_disk(tmp_path):
    fs=load();bad=decision();bad['target']='sha256:archive.tar.gz';ls=ledger(fs,tmp_path,[bad,decision()])
    before=(tmp_path/'judgments.jsonl').read_bytes()
    assert len(ls['issues'])==1 and ls['issues'][0]['line']==1
    assert fs.resolve_judgments(ls,'/a')['topic']['value']=='alpha'
    assert (tmp_path/'judgments.jsonl').read_bytes()==before

def test_content_id_decision_not_guessed_from_path(tmp_path):
    fs=load();r=decision(value='content');r['target']='sha256:'+'a'*64
    ls=ledger(fs,tmp_path,[r]);assert fs.resolve_judgments(ls,'/a')=={}

def test_malformed_json_never_returns_a_partial_ledger(tmp_path):
    p=tmp_path/'judgments.jsonl';p.write_text(json.dumps(decision())+'\n{broken}\n')
    with pytest.raises(ValueError,match='line 2'):load().read_judgments(p)

def test_missing_timezone_is_explicit_invalid_definition(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(ts='2026-01-01')]);assert len(ls['issues'])==1 and not ls['valid']

def test_oversize_input_refused(tmp_path,monkeypatch):
    fs=load();monkeypatch.setattr(fs,'JUDGMENT_LIMIT_BYTES',10);p=tmp_path/'large';p.write_bytes(b'x'*11)
    with pytest.raises(ValueError,match='read bound'):fs.read_judgments(p)

def test_explanation_does_not_stat_payload_or_query_database(tmp_path,monkeypatch,capsys):
    fs=load();ledger(fs,tmp_path,[decision(),decision(field='owner',value='historical')])
    def forbidden(*a,**kw):raise AssertionError('unexpected target or database access')
    monkeypatch.setattr(fs.os,'lstat',forbidden);monkeypatch.setattr(fs.subprocess,'run',forbidden)
    args=SimpleNamespace(index_dir=tmp_path,action='explain',path='/a/does-not-exist')
    assert fs.cmd_judgments(args)==0;result=json.loads(capsys.readouterr().out)
    assert result['facets']['topic']['value']=='alpha'
    assert 'owner' in result['other_fields']
    assert 'no path stat' in result['scope']

def test_audit_only_checks_locations_on_request(tmp_path,monkeypatch,capsys):
    fs=load();ledger(fs,tmp_path,[decision()]);calls=[]
    def absent(path):calls.append(path);raise FileNotFoundError(path)
    monkeypatch.setattr(fs.os,'lstat',absent)
    args=SimpleNamespace(index_dir=tmp_path,action='audit',check_paths=False)
    assert fs.cmd_judgments(args)==0 and calls==[];capsys.readouterr()
    args.check_paths=True;assert fs.cmd_judgments(args)==1
    assert calls==['/a'];assert json.loads(capsys.readouterr().out)['location_counts']=={'missing':1}

def test_report_escapes_markup_and_does_not_copy_other_fields(tmp_path,capsys):
    fs=load();ledger(fs,tmp_path,[decision(value='<tag>|x'),decision(field='owner',value='legacy-owner-value')])
    assert fs.cmd_judgments(SimpleNamespace(index_dir=tmp_path,action='report'))==0
    text=capsys.readouterr().out
    assert '&lt;tag&gt;\\|x' in text and 'legacy-owner-value' not in text

def test_cli_failure_is_bounded_and_has_no_partial_output(tmp_path):
    (tmp_path/'judgments.jsonl').write_text('{broken')
    run=subprocess.run([sys.executable,str(SCRIPT),'judgments','--index-dir',str(tmp_path),'explain','/a'],capture_output=True,text=True,timeout=10)
    assert run.returncode==2 and not run.stdout and 'Malformed JSON' in run.stderr


def test_import_preserves_history_is_idempotent_and_refuses_invalid_batch(tmp_path, capsys):
    fs = load()
    invalid_history = decision()
    invalid_history['target'] = 'sha256:old-filename'
    ledger(fs, tmp_path, [invalid_history, decision(method='operator')])
    original = (tmp_path / 'judgments.jsonl').read_bytes()
    incoming = tmp_path / 'incoming.jsonl'
    incoming.write_text(json.dumps(decision(value='proposal', method='model', ts='2026-02-01T00:00:00Z')) + '\n')
    args = SimpleNamespace(index_dir=tmp_path, action='import', observations=incoming)
    assert fs.cmd_judgments(args) == 0
    assert json.loads(capsys.readouterr().out)['added'] == 1
    updated = (tmp_path / 'judgments.jsonl').read_bytes()
    assert updated.startswith(original)
    assert fs.resolve_judgments(fs.read_judgments(tmp_path / 'judgments.jsonl'), '/a')['topic']['value'] == 'alpha'
    assert fs.cmd_judgments(args) == 0
    assert json.loads(capsys.readouterr().out)['added'] == 0
    assert (tmp_path / 'judgments.jsonl').read_bytes() == updated
    incoming.write_text(json.dumps(decision('/b')) + '\n' + json.dumps(invalid_history) + '\n')
    with pytest.raises(ValueError, match='invalid incoming'):
        fs.cmd_judgments(args)
    assert (tmp_path / 'judgments.jsonl').read_bytes() == updated



def test_canonical_roles_preserve_original_details_and_other_facets(tmp_path,capsys):
    fs=load()
    rows=[decision(field='role',value='very specific legacy capture'),
          decision(field='preservation',value='do not delete'),
          decision(field='maintenance_owner',value='actual owner')]
    old=ledger(fs,tmp_path,rows)
    before=(tmp_path/'judgments.jsonl').read_bytes()
    incoming=tmp_path/'normalization.jsonl'
    new=decision(field='role',value='capture',detail='very specific legacy capture',ts='2026-02-01T00:00:00Z')
    incoming.write_text(json.dumps(new)+'\n')
    args=SimpleNamespace(index_dir=tmp_path,action='import',observations=incoming,expected_sha256=old['sha256'])
    assert fs.cmd_judgments(args)==0
    assert (tmp_path/'judgments.jsonl').read_bytes().startswith(before)
    resolved=fs.resolve_judgments(fs.read_judgments(tmp_path/'judgments.jsonl'),'/a/child')
    assert resolved['role']['value']=='capture'
    assert resolved['role']['details']==['very specific legacy capture']
    assert resolved['preservation']['value']=='do not delete'
    assert resolved['maintenance_owner']['value']=='actual owner'


def test_unknown_new_role_refuses_the_entire_import(tmp_path):
    fs=load();ledger(fs,tmp_path,[decision()]);p=tmp_path/'judgments.jsonl';old=p.read_bytes()
    source=tmp_path/'incoming.jsonl'
    source.write_text(json.dumps(decision('/b',field='role',value='capture'))+'\n'+json.dumps(decision('/c',field='role',value='invented novel category'))+'\n')
    with pytest.raises(ValueError,match='invalid incoming roles'):
        fs.cmd_judgments(SimpleNamespace(action='import',index_dir=tmp_path,observations=source))
    assert p.read_bytes()==old


def test_explicit_legacy_role_import_remains_audit_finding(tmp_path,capsys):
    fs=load();ledger(fs,tmp_path,[decision()]);source=tmp_path/'old.jsonl'
    source.write_text(json.dumps(decision(field='role',value='old descriptive role'))+'\n')
    assert fs.cmd_judgments(SimpleNamespace(action='import',index_dir=tmp_path,observations=source,allow_legacy_roles=True))==0
    capsys.readouterr()
    assert fs.cmd_judgments(SimpleNamespace(action='audit',index_dir=tmp_path,check_paths=False))==1
    result=json.loads(capsys.readouterr().out)
    assert result['role_vocabulary']['noncanonical'][0]['value']=='old descriptive role'


def test_import_stale_review_hash_refused_without_changes(tmp_path):
    fs=load();ledger(fs,tmp_path,[decision()]);p=tmp_path/'judgments.jsonl';old=p.read_bytes()
    source=tmp_path/'new.jsonl';source.write_text(json.dumps(decision('/b'))+'\n')
    with pytest.raises(ValueError,match='changed since review'):
        fs.cmd_judgments(SimpleNamespace(action='import',index_dir=tmp_path,observations=source,expected_sha256='0'*64))
    assert p.read_bytes()==old


def test_role_audit_reads_only_effective_winners_and_does_not_erase_history(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(field='role',value='legacy spelling'),decision(field='role',value='capture',ts='2026-02-01T00:00:00Z')])
    summary=fs.effective_role_audit(ls,['/a','/a/child'])
    assert summary['counts']=={'capture':2} and not summary['noncanonical']
    assert len(ls['valid'])==2


def test_ambiguous_roles_are_not_folded_into_known_categories(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(field='role',value='capture'),decision(field='role',value='analysis')])
    audit=fs.effective_role_audit(ls,['/a'])
    assert audit['counts']=={'[ambiguous]':1}


def test_unknown_role_masks_inheritance_without_forcing_a_category(tmp_path,capsys):
    fs=load();ledger(fs,tmp_path,[decision(field='role',value='capture')])
    source=tmp_path/'new.jsonl';source.write_text(json.dumps(decision('/a/b',field='role',value='not established',observation='unknown'))+'\n')
    assert fs.cmd_judgments(SimpleNamespace(action='import',index_dir=tmp_path,observations=source))==0
    current=fs.read_judgments(tmp_path/'judgments.jsonl')
    assert fs.resolve_judgments(current,'/a/b/child')['role']['status']=='unknown'


@pytest.mark.parametrize('value',[['capture'],{'category':'capture'},42,None])
def test_known_role_requires_a_string_code(tmp_path,value):
    fs=load();ls=ledger(fs,tmp_path,[decision(field='role',value=value)])
    assert fs.validate_role_decisions(ls)


def test_grouped_role_report_retains_detail_and_filters_paths(tmp_path,capsys):
    fs=load();ledger(fs,tmp_path,[decision('/a',field='role',value='capture',detail='sensor capture'),decision('/b',field='role',value='analysis')])
    args=SimpleNamespace(action='report',index_dir=tmp_path,group_by='role',role='capture')
    assert fs.cmd_judgments(args)==0
    text=capsys.readouterr().out
    assert '## capture' in text and 'sensor capture' in text
    assert '| /a |' in text and '| /b |' not in text


def test_equal_category_with_distinct_detail_preserves_both_sources(tmp_path):
    fs=load();ls=ledger(fs,tmp_path,[decision(field='role',value='capture',detail='source A'),decision(field='role',value='capture',detail='source B')])
    got=fs.resolve_judgments(ls,'/a')['role']
    assert got['status']=='known' and got['details']==['source A','source B'] and len(got['evidence'])==2


def test_vocabulary_needs_no_ledger_or_target_access(tmp_path,monkeypatch,capsys):
    fs=load()
    def forbidden(*a,**k):raise AssertionError('unexpected ledger access')
    monkeypatch.setattr(fs,'read_judgments',forbidden)
    assert fs.cmd_judgments(SimpleNamespace(action='vocabulary',index_dir=tmp_path))==0
    out=json.loads(capsys.readouterr().out)
    assert set(out['roles'])==set(fs.ROLE_VOCABULARY) and 'git-origin' in out['roles']


def test_operator_role_is_not_replaced_by_later_normalization(tmp_path,capsys):
    fs=load();ledger(fs,tmp_path,[decision(field='role',value='special operator role',method='operator')])
    source=tmp_path/'new.jsonl';source.write_text(json.dumps(decision(field='role',value='capture',ts='2026-02-01T00:00:00Z'))+'\n')
    assert fs.cmd_judgments(SimpleNamespace(action='import',index_dir=tmp_path,observations=source))==0
    out=fs.resolve_judgments(fs.read_judgments(tmp_path/'judgments.jsonl'),'/a')['role']
    assert out['value']=='special operator role'


def test_ambiguous_role_makes_definition_audit_nonzero(tmp_path,capsys):
    fs=load();ledger(fs,tmp_path,[decision(field='role',value='capture'),decision(field='role',value='analysis')])
    assert fs.cmd_judgments(SimpleNamespace(action='audit',index_dir=tmp_path,check_paths=False))==1
    out=json.loads(capsys.readouterr().out)
    assert out['role_vocabulary']['counts']['[ambiguous]']==1
