"""Offline tests for Configuration's config value cache."""
from fanficfare.configurable import Configuration


def make_configuration(ini=''):
    configuration = Configuration(['test1.com'], 'EPUB')
    configuration.read_string('[defaults]\n' + ini)
    return configuration


def test_default_of_unset_key_is_not_cached_for_other_callers():
    # Regression: the first caller's default was cached as the value
    # of an unset key and returned to callers with other defaults.
    configuration = make_configuration()
    assert configuration.getConfig('datePublished_format',
                                   '%Y-%m-%dT%H:%M:%SZ') == '%Y-%m-%dT%H:%M:%SZ'
    assert configuration.getConfig('datePublished_format',
                                   '%Y-%m-%d') == '%Y-%m-%d'
    assert configuration.getConfig('datePublished_format') == ''


def test_set_key_ignores_defaults():
    configuration = make_configuration('datePublished_format:%%d.%%m.%%Y\n')
    for default in ('%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d', ''):
        assert configuration.getConfig('datePublished_format',
                                       default) == '%d.%m.%Y'
