# -*- coding: utf-8 -*-

# Copyright 2026 FanFicFare team
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

'''
Site independent helpers for finding new stories: author works list
URLs and AO3 tag overlap ("similar stories") search and scoring.  No
network access here, callers fetch the pages with
GetURLs.get_urls_from_page().
'''

import math
import re
from collections import Counter
from urllib.parse import urlencode

## story metadata keys used for tag overlap, and how much a shared tag
## of each kind counts.
TAG_KIND_WEIGHTS = {
    'ships':3.0,
    'characters':2.0,
    'freeformtags':1.0,
    'fandoms':1.0,
    }

## AO3 work search form fields.
AO3_SEARCH_PATH = '/works/search'
AO3_SEARCH_FIELDS = {
    'fandoms':'work_search[fandom_names]',
    'ships':'work_search[relationship_names]',
    'characters':'work_search[character_names]',
    'freeformtags':'work_search[freeform_names]',
    'sort_column':'work_search[sort_column]',
    'sort_direction':'work_search[sort_direction]',
    }
AO3_SORT_COLUMN = 'kudos_count'

def ao3_author_works_url(author_url):
    '''
    The works list of an OTW(AO3 etc) author/pseud URL, or None if
    author_url isn't one (eg Anonymous, other sites).
    '''
    m = re.match(r'^(https?://[^/]+/users/[^/?#]+(/pseuds/[^/?#]+)?)(/works)?/?$',
                 author_url or '')
    if not m:
        return None
    return m.group(1)+'/works'

def get_tags(metadata, kind):
    '''metadata values are lists, or comma separated strings.'''
    val = metadata.get(kind) or []
    if isinstance(val, str):
        val = [ x.strip() for x in val.split(',') ]
    return [ x for x in val if x ]

def build_tag_profile(metadata_list):
    '''
    {kind:{tag:weight}} over the stories' metadata, weight is the
    fraction of the stories that have the tag.
    '''
    metadata_list = list(metadata_list)
    count = max(1, len(metadata_list))
    profile = {}
    for kind in TAG_KIND_WEIGHTS:
        counter = Counter()
        for metadata in metadata_list:
            counter.update(set(get_tags(metadata, kind)))
        profile[kind] = dict( (tag, n/count) for tag, n in counter.items() )
    return profile

def top_tags(profile, kind, n):
    '''Highest weight first, ties by name to keep it stable.'''
    return [ tag for tag, weight in sorted(profile.get(kind,{}).items(),
                                           key=lambda x : (-x[1], x[0])) ][:n]

def make_ao3_search_urls(profile, domain='archiveofourown.org', max_queries=3):
    '''
    Up to max_queries AO3 work search URLs, most kudos first, for the
    profile's top fandom combined with its top ships, or characters
    when there are no ships, and its top freeform tags.
    '''
    fandoms = top_tags(profile, 'fandoms', 1)
    queries = []
    pairs = [ ('ships', [x]) for x in top_tags(profile, 'ships', 2) ]
    if not pairs:
        pairs = [ ('characters', [x]) for x in top_tags(profile, 'characters', 2) ]
    freeforms = top_tags(profile, 'freeformtags', 2)
    if freeforms:
        pairs.append(('freeformtags', freeforms))
    for kind, tags in pairs:
        query = []
        if fandoms:
            query.append((AO3_SEARCH_FIELDS['fandoms'], fandoms[0]))
        query.append((AO3_SEARCH_FIELDS[kind], ','.join(tags)))
        queries.append(query)
    if not queries and fandoms:
        queries.append([(AO3_SEARCH_FIELDS['fandoms'], fandoms[0])])
    urls = []
    for query in queries[:max_queries]:
        query.extend([(AO3_SEARCH_FIELDS['sort_column'], AO3_SORT_COLUMN),
                      (AO3_SEARCH_FIELDS['sort_direction'], 'desc')])
        urls.append('https://%s%s?%s'%(domain, AO3_SEARCH_PATH, urlencode(query)))
    return urls

def to_int(val):
    try:
        return int(str(val).replace(',',''))
    except ValueError:
        return 0

def score_candidates(profile, storydata, exclude_urls=(), limit=50):
    '''
    Rank candidate stories' metadata by tag overlap with profile.
    Returns [(score, [matched tags], metadata)], best first, without
    stories sharing no tags or with storyUrl in exclude_urls.

    Shared tags count by kind weight times their weight in the
    profile, divided by the square root of the candidate's tag count
    so stories don't win by tagging everything.
    '''
    exclude_urls = set(exclude_urls)
    seen = set()
    scored = []
    for metadata in storydata:
        url = metadata.get('storyUrl')
        if not url or url in exclude_urls or url in seen:
            continue
        seen.add(url)
        score = 0.0
        matched = []
        tagcount = 0
        for kind, kindweight in TAG_KIND_WEIGHTS.items():
            tags = get_tags(metadata, kind)
            tagcount += len(tags)
            for tag in tags:
                weight = profile.get(kind,{}).get(tag)
                if weight:
                    score += kindweight * weight
                    matched.append(tag)
        if score:
            scored.append((score / math.sqrt(max(1, tagcount)), matched, metadata))
    scored.sort(key=lambda x : (-x[0], -to_int(x[2].get('kudos',0))))
    return scored[:limit]
