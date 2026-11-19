"""Offline tests for AO3 list pages (author/tag/search works) in
get_urls_from_page: blurb metadata and paging."""
import os
from urllib.parse import urlparse, parse_qs

import pytest

from fanficfare import adapters
from fanficfare.configurable import Configuration
from fanficfare.geturls import GetURLs


def blurb(workid, title, ships=(), characters=(), freeforms=(), fandom='Fandom A'):
    tags = ''.join('<li class="relationships"><a class="tag" href="/tags/x/works">%s</a></li>' % x for x in ships)
    tags += ''.join('<li class="characters"><a class="tag" href="/tags/x/works">%s</a></li>' % x for x in characters)
    tags += ''.join('<li class="freeforms"><a class="tag" href="/tags/x/works">%s</a></li>' % x for x in freeforms)
    return '''
<li id="work_%(id)s" class="work blurb group" role="article">
  <div class="header module">
    <h4 class="heading">
      <a href="/works/%(id)s">%(title)s</a>
      by
      <a rel="author" href="/users/auth/pseuds/auth">auth</a>
    </h4>
    <h5 class="fandoms heading">
      <a class="tag" href="/tags/Fandom%%20A/works">%(fandom)s</a>
    </h5>
    <p class="datetime">10 Jul 2026</p>
  </div>
  <ul class="tags commas">
    <li class="warnings"><strong><a class="tag" href="/tags/x/works">No Archive Warnings Apply</a></strong></li>
    %(tags)s
  </ul>
  <blockquote class="userstuff summary"><p>Summary %(id)s</p></blockquote>
  <dl class="stats">
    <dt class="language">Language:</dt><dd class="language">English</dd>
    <dt class="words">Words:</dt><dd class="words">1,000</dd>
    <dt class="chapters">Chapters:</dt><dd class="chapters"><a href="/works/%(id)s/chapters/1">2</a>/2</dd>
    <dt class="kudos">Kudos:</dt><dd class="kudos"><a href="/works/%(id)s/kudos">50</a></dd>
  </dl>
</li>''' % {'id': workid, 'title': title, 'tags': tags, 'fandom': fandom}


def page(blurbs, base, maxpage):
    pagination = ''
    if maxpage > 1:
        pagination = '<ol class="pagination actions">%s</ol>' % ''.join(
            '<li><a href="%s%spage=%d">%d</a></li>' % (base, '&' if '?' in base else '?', n, n)
            for n in range(2, maxpage + 1))
    return '''<html><body><div id="main">
<h2 class="heading">1 - 2 of %d Works by auth</h2>
<ol class="work index group">%s</ol>
%s
</div></body></html>''' % (maxpage * 2, ''.join(blurbs), pagination)


@pytest.fixture
def configuration(tmp_path):
    def make(max_listing_pages=None):
        configuration = Configuration(['archiveofourown.org'], 'EPUB', lightweight=True)
        configuration.read(os.path.join(
            os.path.dirname(__file__), '..', '..', 'fanficfare', 'defaults.ini'))
        if max_listing_pages is not None:
            personal = tmp_path / 'personal.ini'
            personal.write_text('[archiveofourown.org]\nmax_listing_pages:%s\n' % max_listing_pages)
            configuration.read(str(personal))
        return configuration
    return make


def run_listing(monkeypatch, configuration, url, pages):
    '''pages: {pagenum: html}.  Returns (result, requested urls).'''
    requested = []

    def fake_get_request(self, url, usecache=True):
        requested.append(url)
        pagenum = int(parse_qs(urlparse(url).query).get('page', ['1'])[0])
        return pages[pagenum]

    from fanficfare.adapters.base_adapter import BaseSiteAdapter
    monkeypatch.setattr(BaseSiteAdapter, 'get_request', fake_get_request)
    geturls = GetURLs(configuration)
    return geturls.get_urls_from_page(url), requested


@pytest.mark.parametrize('url,expected', [
    ('https://archiveofourown.org/users/auth/works', True),
    ('https://archiveofourown.org/users/auth/pseuds/other/works', True),
    ('https://archiveofourown.org/users/auth/works?page=2', True),
    ('https://archiveofourown.org/tags/Fandom%20A/works', True),
    ('https://archiveofourown.org/tags/A*s*B/works?work_search%5Bsort_column%5D=kudos_count', True),
    ('https://archiveofourown.org/collections/coll/works', True),
    ('https://archiveofourown.org/works/search?work_search%5Bquery%5D=x', True),
    ('https://archiveofourown.org/works?work_search%5Bquery%5D=x', True),
    ('https://archiveofourown.org/works/12345', False),
    ('https://archiveofourown.org/series/12345', False),
    ('https://archiveofourown.org/users/auth/bookmarks', False),
    ('https://archiveofourown.org/users/auth', False),
])
def test_is_listing_url(configuration, url, expected):
    adapter = adapters.getAdapter(configuration(), url, anyurl=True)
    assert adapter.is_listing_url(url) == expected


def test_listing_blurb_metadata(monkeypatch, configuration):
    url = 'https://archiveofourown.org/users/auth/works'
    html = page([blurb(111, 'One', ships=['A/B'], characters=['A', 'B'], freeforms=['Fluff']),
                 blurb(222, 'Two', ships=['C/D'])], url, 1)
    result, requested = run_listing(monkeypatch, configuration(), url, {1: html})

    assert result['urllist'] == ['https://archiveofourown.org/works/111',
                                 'https://archiveofourown.org/works/222']
    assert requested == [url]
    assert result['name'] == '1 - 2 of 2 Works by auth'
    assert 'desc' not in result
    first = result['storydata'][0]
    assert first['title'] == 'One'
    assert first['author'] == ['auth']
    assert first['ships'] == ['A/B']
    assert first['characters'] == ['A', 'B']
    assert first['freeformtags'] == ['Fluff']
    assert first['fandoms'] == ['Fandom A']
    assert first['status'] == 'Completed'


def test_listing_pages_limited(monkeypatch, configuration):
    url = 'https://archiveofourown.org/tags/X/works?work_search%5Bsort_column%5D=kudos_count'
    pages = dict((n, page([blurb(n * 10 + 1, 'a%d' % n), blurb(n * 10 + 2, 'b%d' % n)], url, 6))
                 for n in range(1, 7))
    result, requested = run_listing(monkeypatch, configuration(max_listing_pages=3), url, pages)

    assert len(requested) == 3
    assert len(result['urllist']) == 6
    # search params are kept on later pages.
    for pageurl, n in zip(requested[1:], (2, 3)):
        query = parse_qs(urlparse(pageurl).query)
        assert query['page'] == [str(n)]
        assert query['work_search[sort_column]'] == ['kudos_count']


def test_listing_starts_at_given_page(monkeypatch, configuration):
    url = 'https://archiveofourown.org/users/auth/works?page=2'
    pages = dict((n, page([blurb(n, 'a%d' % n)], 'https://archiveofourown.org/users/auth/works', 4))
                 for n in range(1, 5))
    result, requested = run_listing(monkeypatch, configuration(max_listing_pages=2), url, pages)

    assert result['urllist'] == ['https://archiveofourown.org/works/2',
                                 'https://archiveofourown.org/works/3']
    assert len(requested) == 2
