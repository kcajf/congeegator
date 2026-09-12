"""Preserve lexical relationships without guessing markup or language targets."""
import json
import sqlite3

import msgspec

from pipeline.dictionary import (DICT_CONFIGS, extract_examples, extract_senses,
    extract_etymology, extract_etymology_links, process_dict_entry, word_link)
from pipeline.sqlite_output import write_sqlite_database
from pipeline.wiktionary import Entry, EtymologyTemplate, Sense, FormOf


def entry(**kw):
    return Entry(**(dict(word='manchen', lang_code='de', lang='German', pos='pron') | kw))


def test_form_of_overrides_unanchored_english_link_and_retains_grammar():
    senses = extract_senses(entry(senses=(Sense(
        glosses=('inflection of manch:', 'dative plural'),
        links=(('manch', 'manch'),), form_of=(FormOf('manch'),)),)))
    assert senses[0]['gloss'] == 'inflection of manch: dative plural'
    assert senses[0]['links'] == [{'word': 'manch', 'lang': 'de'}]
    assert senses[0]['formOf'] == senses[0]['links']


def test_alternative_and_definition_targets_are_distinct():
    sense = extract_senses(entry(senses=(Sense(glosses=('alternative of Haus; a house',),
        alt_of=(FormOf('Haus'),), links=(('house', 'house'),)),)))[0]
    assert sense['altOf'] == [{'word': 'Haus', 'lang': 'de'}]
    assert {'word': 'house', 'lang': 'en'} in sense['links']


def test_anchors_and_display_labels():
    assert word_link('ψηφοφορία#Greek', 'en', 'voting') == {'word':'ψηφοφορία','lang':'el','label':'voting'}
    assert word_link('recipe#Noun', 'en')['lang'] == 'en'
    assert word_link('word#Old_English', 'en') == {'word':'word','lang':'','anchor':'Old_English'}
    for target in ('w:Politics','Category:Politics','https://example.com','{{bad}}','-','*root'):
        assert word_link(target,'en') is None


def test_translations_bold_offsets_and_quotation_attribution():
    examples=extract_examples([{'text':'  𐌖 aqua  ', 'bold_text_offsets':[[4,8]],
        'english':'water', 'bold_translation_offsets':[[0,5]], 'type':'quotation', 'ref':'A source'}])
    assert examples == [{'text':'𐌖 aqua', 'translation':'water', 'bold':[[2,6]],
        'translationBold':[[0,5]], 'type':'quotation', 'ref':'A source'}]


def test_bad_example_metadata_does_not_remove_valid_text():
    examples=extract_examples([{'text':'a house', 'translation':'(please add an English translation)',
        'bold_text_offsets':[[-1,5],[0,100],['0',2],[True,3],[2,7]]}, {'text':'a house'}])
    assert examples == [{'text':'a house','bold':[[2,7]]}]


def test_topics_use_explicit_labels_and_relations_keep_sense():
    value=entry(senses=(Sense(glosses=('vote',),raw_glosses=('(politics) vote',),
        topics=('government','politics'), synonyms=({'word':'Abstimmung'},{'word':'Abstimmung'})),),
        derived=({'word':'Wahlrecht','sense':'voting','tags':['rare']},))
    result=process_dict_entry(DICT_CONFIGS[2],value)
    assert result['senses'][0]['topics'] == ['politics']
    assert result['senses'][0]['synonyms'] == [{'word':'Abstimmung','lang':'de'}]
    assert result['details']['derived'] == [{'word':'Wahlrecht','lang':'de','sense':'voting','tags':['rare']}]


def test_full_etymology_survives_and_templates_preserve_display_target():
    value=entry(etymology_text='From Latin mānsiōnem, with a longer explanation.', etymology_templates=(
        EtymologyTemplate('inh', {'1':'fr','2':'la','3':'mānsiō','4':'mānsiōnem'}, 'Latin mānsiōnem'),
        EtymologyTemplate('etymon', {}, 'broken template data'),))
    assert extract_etymology(value) == value.etymology_text
    assert extract_etymology_links(value) == [{'word':'mānsiō','lang':'la','label':'mānsiōnem'}]


def test_etymology_tree_is_not_repeated_as_flat_prose():
    assert extract_etymology(entry(word='Haus',etymology_text='Etymology tree\nGerman Haus\nFrom Middle High German hūs.')) == 'From Middle High German hūs.'


def test_optional_rich_fields_decode_without_affecting_conjugation_model():
    value=msgspec.json.decode(json.dumps({'word':'casa','pos':'noun','lang_code':'pt','lang':'Portuguese',
        'senses':[{'glosses':['house'],'links':[['house','house']],'examples':[{'text':'casa','translation':'house'}]}],
        'derived':[{'word':'casinha'}],'etymology_text':'From Latin casa.'}),type=Entry)
    result=process_dict_entry(DICT_CONFIGS[6],value)
    assert result['details']['derived'][0]['word']=='casinha'
    assert result['senses'][0]['examples'][0]['translation']=='house'


def test_indexed_form_lookup_is_exact_deduplicated_and_retains_rich_json(tmp_path):
    entries=[{'word':'sich auf den Weg machen','pos':'verb','senses':[{'gloss':'hit the road','links':[{'word':'hit the road','lang':'en'}]}],
        'forms':['machte sich auf den Weg','machte sich auf den Weg','macht sich auf den Weg'],
        'details':{'synonyms':[{'word':'aufbrechen','lang':'de'}]}}]
    path=str(tmp_path/'de.sqlite')
    write_sqlite_database(entries,'de',None,path)
    with sqlite3.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM form_lookup').fetchone()[0]==2
        assert conn.execute('SELECT entry_id FROM form_lookup WHERE form_key=?',('machte sich auf den weg',)).fetchall()==[(0,)]
        assert not conn.execute('SELECT entry_id FROM form_lookup WHERE form_key=?',('machte weg',)).fetchall()
        plan=conn.execute('EXPLAIN QUERY PLAN SELECT entry_id FROM form_lookup WHERE form_key=?',('x',)).fetchall()
        assert any('PRIMARY KEY' in row[3] for row in plan)
        assert json.loads(conn.execute('SELECT details FROM entries').fetchone()[0])==entries[0]['details']
        assert json.loads(conn.execute('SELECT senses FROM entries').fetchone()[0])==entries[0]['senses']


def test_doublets_are_independent_terms_not_display_aliases():
    value=entry(etymology_templates=(EtymologyTemplate('doublet',{'1':'fr','2':'parabole','3':'palabre'}),))
    assert extract_etymology_links(value)==[{'word':'parabole','lang':'fr'},{'word':'palabre','lang':'fr'}]


def test_affix_overrides_and_borrowing_aliases():
    value=entry(etymology_templates=(
        EtymologyTemplate('affix',{'1':'fr','2':'machja','lang1':'co','alt1':'mac(c)hja','3':'-is'}),
        EtymologyTemplate('lbor',{'1':'fr','2':'la','3':'casa'}),
        EtymologyTemplate('affix',{'1':'en','2':'word<id:meaning>','3':'-ness'})))
    assert extract_etymology_links(value)==[{'word':'machja','lang':'co','label':'mac(c)hja'},
        {'word':'-is','lang':'fr'},{'word':'casa','lang':'la'},{'word':'-ness','lang':'en'}]


def test_labels_do_not_match_substrings_or_definition_body():
    result=extract_senses(entry(senses=(Sense(glosses=('a protein used in chemistry',),
        raw_glosses=('(biochemistry) a protein used in chemistry',), topics=('biochemistry','chemistry'),
        tags=('figuratively','ambitransitive')),)))[0]
    assert result['topics']==['biochemistry']
    assert result['tags']==['figuratively','ambitransitive']


def test_synonym_qualifiers_are_retained():
    result=extract_senses(entry(senses=(Sense(glosses=('mendacious',),synonyms=(
        {'word':'bastard','tags':['synonym'],'raw_tags':['of plant species']},)),)))[0]
    assert result['synonyms'][0]['tags']==['of plant species']


def test_usage_examples_precede_quotes_and_reject_broken_wiki_emphasis():
    result=extract_examples([{'text':"Star Wars'''y",'type':'quotation'},
        {'text':'a quotation','type':'quotation'},{'text':'a usage example','type':'example'}])
    assert [example['text'] for example in result]==['a usage example','a quotation']


def test_source_page_titles_resolve_stressed_lemma_and_aspect_labels():
    for lang, label, target, form_word in [('ru','стыди́ться','стыдиться','стыди́ться'),
            ('uk','розряди́ти','розрядити','розряди́ти pf'),('la','trānsfōrmandus','transformandus','trānsfōrmandus')]:
        value=entry(lang_code=lang,senses=(Sense(glosses=(f'inflection of {label}',),
            form_of=(FormOf(form_word),),links=((label,target),)),))
        sense=extract_senses(value)[0]
        assert sense['formOf']==[{'word':target,'lang':lang,'label':label}]
        assert sense['links']==sense['formOf']


def test_underscore_language_anchor_stays_local():
    assert word_link('sjal#Norwegian_Bokmål','en')=={'word':'sjal','lang':'nb'}


def test_citation_survives_missing_date_placeholder():
    example=extract_examples([{'text':'a quotation','ref':'Author, Title (please provide the date):','type':'quotation'}])[0]
    assert example['ref']=='Author, Title :'
