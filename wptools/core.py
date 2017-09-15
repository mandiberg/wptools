# -*- coding:utf-8 -*-

"""
WPTools core module
~~~~~~~~~~~~~~~~~~~

Support for accessing Wikimedia foundation APIs.
"""

from wptools.query import WPToolsQuery

from . import request
from . import utils


class WPTools(object):
    """
    WPtools (abstract) core class
    """

    cache = None
    data = None
    flags = None
    params = None

    def __init__(self, *args, **kwargs):
        """
        Abstract initialization for...
        - wptools.page
        - wptools.category
        - wptools.restbase
        - wptools.wikidata
        """
        self.cache = {}
        self.data = {}

        self.flags = {
            'silent': kwargs.get('silent') or False,
            'verbose': kwargs.get('verbose') or False
        }

        self.params = {
            'lang': kwargs.get('lang') or 'en',
        }

        if len(args) > 0 and args[0]:  # first positional arg is title
            self.params.update({'title': args[0]})

        if kwargs.get('skip'):
            self.flags.update({'skip': kwargs.get('skip')})

        if kwargs.get('variant'):
            self.params.update({'variant': kwargs.get('variant')})

        if kwargs.get('wiki'):
            self.params.update({'wiki': kwargs.get('wiki')})

    def _get(self, action, show, proxy, timeout):
        """
        make HTTP request and cache response
        """
        silent = self.flags['silent']

        if action in self.cache:
            if action != 'imageinfo':
                utils.stderr("+ %s results in cache" % action, silent)
                return
        else:
            self.cache[action] = {}

        if self.flags.get('skip') and action in self.flags['skip']:
            if not self.flags['silent']:
                utils.stderr("+ skipping %s" % action)
            return

        # make the request
        qobj = WPToolsQuery(lang=self.params['lang'],
                            wiki=self.params.get('wiki'),
                            variant=self.params.get('variant'))
        qstr = self._query(action, qobj)
        self.cache[action]['query'] = qstr

        req = self._request(proxy, timeout)
        response = req.get(qstr, qobj.status)
        self.cache[action]['response'] = response
        self.cache[action]['info'] = req.info

        self._set_data(action)

        if show:
            self.show()

    def _load_response(self, action):
        """
        returns API reponse from cache or raises ValueError
        """
        _query = self.cache[action]['query'].replace('&format=json', '')
        response = self.cache[action]['response']

        if not response:
            raise ValueError("Empty response: %s" % self.params)

        try:
            data = utils.json_loads(response)
        except ValueError:
            raise ValueError(_query)

        if data.get('warnings'):
            utils.stderr("API warning: %s" % data.get('warnings'))

        if data.get('error'):
            utils.stderr("API error: %s" % data.get('error'))
            raise LookupError(_query)

        if 'query' in action and data.get('query'):
            if data['query'].get('pages'):
                if data['query']['pages'][0].get('missing'):
                    raise LookupError(_query)

        if action == 'parse' and not data.get('parse'):
            raise LookupError(_query)

        if action == 'wikidata' and '-1' in data.get('entities'):
            raise LookupError(_query)

        return data

    def _query(self, action, qobj):
        """
        Abstract method that returns WPToolsQuery string
        """
        raise NotImplementedError("A subclass must implement this method.")

    def _request(self, proxy, timeout):
        """
        Returns WPToolsRequest object
        """
        return request.WPToolsRequest(self.flags['silent'],
                                      self.flags['verbose'],
                                      proxy, timeout)

    def _set_data(self, action):
        """
        Abstract method to capture API response data
        """
        raise NotImplementedError("A subclass must implement this method.")

    def info(self, action=None):
        """
        returns cached request info for given action,
        or list of cached actions
        """
        if action in self.cache:
            return self.cache[action]['info']
        return self.cache.keys() or None

    def query(self, action=None):
        """
        returns cached query string (without &format=json) for given action,
        or list of cached actions
        """
        if action in self.cache:
            return self.cache[action]['query'].replace('&format=json', '')
        return self.cache.keys() or None

    def response(self, action=None):
        """
        returns cached response (as dict) for given action,
        or list of cached actions
        """
        if action in self.cache:
            return utils.json_loads(self.cache[action]['response'])
        return self.cache.keys() or None

    def show(self):
        """
        Pretty-print instance data
        """
        if self.flags.get('silent') or not self.data:
            return

        ptitle = self.params.get('title')
        dtitle = self.data.get('title')
        pageid = self.params.get('pageid')

        seed = dtitle or ptitle or pageid
        if utils.is_text(seed):
            seed = seed.replace('_', ' ')

        output = ["%s (%s) data" % (seed, self.params['lang'])]

        output.append('{')

        maxwidth = WPToolsQuery.MAXWIDTH

        for item in sorted(self.data):

            if self.data[item] is None:
                continue

            prefix = item
            value = self.data[item]

            if isinstance(value, dict):
                prefix = "%s: <dict(%d)>" % (prefix, len(value))
                value = ', '.join(value.keys())
            elif isinstance(value, int):
                prefix = "%s:" % prefix
            elif isinstance(value, list):
                prefix = "%s: <list(%d)>" % (prefix, len(value))
                value = ', '.join((safestr(x) for x in value if x))
            elif isinstance(value, tuple):
                prefix = "%s: <tuple(%d)>" % (prefix, len(value))
                value = ', '.join((safestr(x) for x in value if x))
            elif utils.is_text(value):
                value = value.strip().replace('\n', '')
                if len(value) > (maxwidth - len(prefix)):
                    prefix = "%s: <str(%d)>" % (prefix, len(value))
                else:
                    prefix = "%s:" % prefix

            output.append("  %s %s" % (prefix, value))

        output.append('}')

        prettyprint(output)


def prettyprint(datastr):
    """
    Print page data strings to stderr
    """
    maxwidth = WPToolsQuery.MAXWIDTH
    rpad = WPToolsQuery.RPAD

    extent = maxwidth - (rpad + 2)
    for line in datastr:
        if len(line) >= maxwidth:
            line = line[:extent] + '...'
        utils.stderr(line)


def safestr(text):
    """
    Safely convert unicode to a string
    """
    if text is None:
        return
    try:
        return str(text)
    except UnicodeEncodeError:
        return str(text.encode('utf-8'))
