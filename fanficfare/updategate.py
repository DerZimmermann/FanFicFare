'''
Shared update-count decision logic for cli.py, calibre-plugin/jobs.py
and calibre-plugin/fff_plugin.py.

Returns a string decision so each caller can keep its own messaging and
error handling:

  'already_contains'  -- existing file and site have the same chapter
                         count and no recheck/edit detection needed.
  'more_than_source'  -- existing file has more chapters than the site and
                         deleted chapters are not being preserved.
  'no_chapters'       -- no recognizable chapters in the existing file.
  'proceed'           -- do the update.
'''


def decide_update(chaptercount, urlchaptercount,
                  metaonly=False,
                  updatealways=False,
                  needs_edit_check=False,
                  preserve_deleted=False,
                  force_update_epub_always=False):
    # Equal counts usually mean nothing to do, but keep going when
    # preserving deleted chapters so equal numbers of deleted and new
    # chapters can be swapped.
    if chaptercount == urlchaptercount and not metaonly and not updatealways \
            and not needs_edit_check and not preserve_deleted:
        return 'already_contains'
    if chaptercount > urlchaptercount and not preserve_deleted \
            and not (updatealways and force_update_epub_always):
        return 'more_than_source'
    if chaptercount == 0:
        return 'no_chapters'
    return 'proceed'

def count_chapter_changes(chaptercount, old_chapter_urls, site_chapter_urls):
    '''
    Count what an update would change without downloading anything:
    returns (new_count, removed_count), the chapters on the site that
    aren't in the existing file yet and the chapters in the existing
    file that are no longer on the site.

    Updates match chapters by URL, so old_chapter_urls must already be
    normalized the same way adapter.getStory() normalizes
    oldchaptersmap.  Failed (continue_on_chapter_error) chapters aren't
    in old_chapter_urls, so they count as new, same as an update would
    download them again.  Files without chapter URLs (very old epubs)
    are updated by chapter position, so only counts are compared.
    '''
    site_chapter_urls = list(site_chapter_urls)
    old_chapter_urls = set(old_chapter_urls)
    if not old_chapter_urls:
        sitecount = len(site_chapter_urls)
        return (max(0, sitecount - chaptercount),
                max(0, chaptercount - sitecount))
    new_count = len([ url for url in site_chapter_urls
                      if url not in old_chapter_urls ])
    removed_count = len(old_chapter_urls - set(site_chapter_urls))
    return (new_count, removed_count)
