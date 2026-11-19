# -*- coding: utf-8 -*-
"""Tag overlap search/scoring and author works URLs for finding new
stories."""
from urllib.parse import urlparse, parse_qs

import pytest

from fanficfare.discover import (ao3_author_works_url, build_tag_profile,
                                 make_ao3_search_urls, score_candidates)


@pytest.mark.parametrize('url,expected', [
    ('https://archiveofourown.org/users/auth/pseuds/pen',
     'https://archiveofourown.org/users/auth/pseuds/pen/works'),
    ('https://archiveofourown.org/users/auth',
     'https://archiveofourown.org/users/auth/works'),
    ('https://archiveofourown.org/users/auth/works',
     'https://archiveofourown.org/users/auth/works'),
    ('https://archiveofourown.org/users/auth/',
     'https://archiveofourown.org/users/auth/works'),
    ('https://squidgeworld.org/users/auth/pseuds/auth',
     'https://squidgeworld.org/users/auth/pseuds/auth/works'),
    # Anonymous on AO3.
    ('https://archiveofourown.org/', None),
    ('https://www.fanfiction.net/u/12345/name', None),
    ('', None),
    (None, None),
])
def test_ao3_author_works_url(url, expected):
    assert ao3_author_works_url(url) == expected


BOOKS = [
    {'fandoms': ['F1'], 'ships': ['A/B'], 'characters': ['A', 'B'],
     'freeformtags': ['Fluff', 'Angst']},
    {'fandoms': ['F1'], 'ships': ['A/B', 'C/D'], 'characters': ['A'],
     'freeformtags': ['Fluff']},
    # comma separated strings work too.
    {'fandoms': 'F1, F2', 'ships': 'A/B', 'characters': 'A, C',
     'freeformtags': 'Hurt/Comfort'},
]


def test_build_tag_profile():
    profile = build_tag_profile(BOOKS)
    assert profile['fandoms'] == {'F1': 1.0, 'F2': pytest.approx(1/3)}
    assert profile['ships'] == {'A/B': 1.0, 'C/D': pytest.approx(1/3)}
    assert profile['characters']['A'] == 1.0
    assert profile['freeformtags']['Fluff'] == pytest.approx(2/3)


def test_build_tag_profile_empty():
    assert build_tag_profile([]) == {'ships': {}, 'characters': {},
                                     'freeformtags': {}, 'fandoms': {}}


def query_of(url):
    parts = urlparse(url)
    assert parts.netloc == 'archiveofourown.org'
    assert parts.path == '/works/search'
    return parse_qs(parts.query)


def test_make_ao3_search_urls():
    urls = make_ao3_search_urls(build_tag_profile(BOOKS))
    assert len(urls) == 3
    queries = [query_of(x) for x in urls]
    for q in queries:
        assert q['work_search[fandom_names]'] == ['F1']
        assert q['work_search[sort_column]'] == ['kudos_count']
        assert q['work_search[sort_direction]'] == ['desc']
    assert queries[0]['work_search[relationship_names]'] == ['A/B']
    assert queries[1]['work_search[relationship_names]'] == ['C/D']
    assert queries[2]['work_search[freeform_names]'] == ['Fluff,Angst']


def test_make_ao3_search_urls_max_and_fallbacks():
    profile = build_tag_profile(BOOKS)
    assert len(make_ao3_search_urls(profile, max_queries=1)) == 1

    # no ships: characters instead.
    nochars = build_tag_profile([{'fandoms': ['F1'], 'characters': ['A']}])
    q = query_of(make_ao3_search_urls(nochars)[0])
    assert q['work_search[character_names]'] == ['A']

    # fandom only.
    onlyfandom = build_tag_profile([{'fandoms': ['F1']}])
    urls = make_ao3_search_urls(onlyfandom)
    assert len(urls) == 1
    assert 'work_search[relationship_names]' not in query_of(urls[0])

    # nothing to search for.
    assert make_ao3_search_urls(build_tag_profile([{}])) == []


def test_make_ao3_search_urls_domain_and_encoding():
    profile = build_tag_profile([{'fandoms': ['Fandom & Co.'], 'ships': ['A/B']}])
    url = make_ao3_search_urls(profile, domain='squidgeworld.org')[0]
    assert url.startswith('https://squidgeworld.org/works/search?')
    assert ' ' not in url and '&Co' not in url
    q = parse_qs(urlparse(url).query)
    assert q['work_search[fandom_names]'] == ['Fandom & Co.']


def cand(n, kudos='0', **tags):
    d = {'storyUrl': 'https://archiveofourown.org/works/%d' % n, 'kudos': kudos}
    d.update(tags)
    return d


def test_score_candidates_order_and_matches():
    profile = build_tag_profile(BOOKS)
    candidates = [
        cand(1, fandoms=['F1']),
        cand(2, fandoms=['F1'], ships=['A/B'], characters=['A']),
        cand(3, fandoms=['Other'], ships=['X/Y']),          # no overlap
        cand(4, fandoms=['F1'], ships=['A/B'], characters=['A'],
             freeformtags=['t%d' % i for i in range(30)]),  # tag spam
    ]
    scored = score_candidates(profile, candidates)
    urls = [x[2]['storyUrl'] for x in scored]
    assert urls == ['https://archiveofourown.org/works/2',
                    'https://archiveofourown.org/works/4',
                    'https://archiveofourown.org/works/1']
    assert scored[0][1] == ['A/B', 'A', 'F1']


def test_score_candidates_excludes_dups_limit_and_kudos_ties():
    profile = build_tag_profile(BOOKS)
    candidates = [
        cand(1, kudos='10', ships=['A/B']),
        cand(2, kudos='1,200', ships=['A/B']),
        cand(2, kudos='1,200', ships=['A/B']),
        cand(3, ships=['A/B']),
        {'ships': ['A/B']},  # no storyUrl
    ]
    scored = score_candidates(profile, candidates,
                              exclude_urls={'https://archiveofourown.org/works/3'})
    assert [x[2]['storyUrl'][-1] for x in scored] == ['2', '1']
    assert len(score_candidates(profile, candidates, limit=1)) == 1
