"""Mailbox data must neither select agents nor lose text during intent parsing."""
import pytest
from sqlmodel import select

from app.custom_agents import custom_agent_mentions
from app.intent_decisions import strip_mentions
from app.models import Session
from app.planning_intents import MentionParseError, parse_frontend_intent, parse_mentions
from test_group_planning import db, custom


@pytest.mark.parametrize('address', [
    'ada@example.com', 'ADA@EXAMPLE.COM', 'first.last+tag@example-domain.org',
    'ops@frontend.example', 'frontend@qa', '用户@example.com',
    'jose\u0301@example.com', 'रवि@example.com',
])
def test_email_does_not_add_recipient_or_reject_a_real_group(db, address):
    workspace_id = db.exec(select(Session)).one().workspace_id
    parsed = parse_mentions(db, f'请@frontend修复联系人 {address}，再由@qa复查。', workspace_id)
    assert parsed.roles == ['frontend', 'qa']
    assert not parsed.profile_ids


def test_custom_alias_in_mailbox_does_not_select_a_disabled_agent(db):
    profile = custom(db)
    profile.status = 'disabled'
    db.add(profile); db.commit()
    text = 'Review contact ops@ui-expert.example'
    assert custom_agent_mentions(db, profile.workspace_id, text) == {}
    assert parse_mentions(db, text, profile.workspace_id).roles == []
    with pytest.raises(MentionParseError, match='disabled'):
        parse_mentions(db, '@ui-expert Review contacts', profile.workspace_id)


def test_email_does_not_create_ambiguous_custom_and_builtin_recipients(db):
    profile = custom(db)
    parsed = parse_mentions(db, 'ops@frontend.example @ui-expert update demo app', profile.workspace_id)
    assert parsed.roles == ['frontend']
    assert parsed.profile_ids == {'frontend': profile.id}


def test_literal_mailbox_copy_is_preserved_in_intent_parameters():
    intent = parse_frontend_intent('@frontend change button text to support@example.com')
    assert intent is not None
    assert intent.target_text == 'support@example.com'
    assert strip_mentions('@qa explain alice@frontend.test and a@qa plus `x@y.z`') == ' explain alice@frontend.test and a@qa plus `x@y.z`'


@pytest.mark.parametrize('address', ['jose\u0301@example.com', 'रवि@example.com'])
def test_combining_marks_are_preserved_in_copy_values(address):
    intent = parse_frontend_intent(f'@frontend change button text to {address}')
    assert intent is not None
    assert intent.target_text == address


@pytest.mark.parametrize('text,roles', [
    ('请@frontend处理，并由@qa复查。', ['frontend', 'qa']),
    ('@frontend. Please ask @qa.', ['frontend', 'qa']),
    ('Contact ada@example.com; @qa', ['qa']),
    ('Quoted `@frontend` and "@ghost"; @qa', ['qa']),
])
def test_real_adjacent_and_punctuation_mentions_keep_the_existing_contract(db, text, roles):
    assert parse_mentions(db, text).roles == roles


def test_explicit_unknown_alias_still_fails_after_email_data(db):
    with pytest.raises(MentionParseError, match='@ghost'):
        parse_mentions(db, 'ada@example.com @ghost review')
    with pytest.raises(MentionParseError, match='@ghost'):
        parse_mentions(db, '@ghost.example review')
