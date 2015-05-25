import re
import urllib

REGEXP_TYPE = type(re.compile(''))
PATH_REGEXP = re.compile('|'.join([
    # Match escaped characters that would otherwise appear in future matches.
    # This allows the user to escape special characters that won't transform.
    '(\\\\.)',
    # Match Express-style parameters and un-named parameters with a prefix
    # and optional suffixes. Matches appear as:
    #
    # "/:test(\\d+)?" => ["/", "test", "\d+", undefined, "?", undefined]
    # "/route(\\d+)"  => [undefined, undefined, undefined, "\d+", undefined, undefined]
    # "/*"            => ["/", undefined, undefined, undefined, undefined, "*"]
    '([\\/.])?(?:(?:\\:(\\w+)(?:\\(((?:\\\\.|[^()])+)\\))?|\\(((?:\\\\.|[^()])+)\\))([+*?])?|(\\*))'
]))


def parse(string):
    """
    Parse a string for the raw tokens.

    Return array of tokens

    """
    tokens = []
    key = 0
    index = 0
    path = ''

    for match in PATH_REGEXP.finditer(string):
        if match is None:
            break

        matched = match.group(0)
        escaped = match.group(1)
        offset = match.start(0)
        path += string[index:offset]
        index = offset + len(matched)

        if escaped:
            path += escaped[1]
            continue

        if path:
            tokens.append(path)
            path = ''

        prefix, name, capture, group, suffix, asterisk = match.groups()[1:]
        repeat = suffix in ('+', '*')
        optional = suffix in ('?', '*')
        delimiter = prefix or '/'
        pattern = capture or group or ('.*' if asterisk else '[^%s]+?' % delimiter)

        if not name:
            name = key
            key += 1

        token = {
            'name': str(name),
            'prefix': prefix or '',
            'delimiter': delimiter,
            'optional': optional,
            'repeat': repeat,
            'pattern': escape_group(pattern),
        }

        tokens.append(token)

    if index < len(string):
        path += string[index:]

    if path:
        tokens.append(path)

    return tokens


def compile(string):
    """
    Compile a string to a template function for the path.

    """
    return tokens_to_function(parse(string))


def tokens_to_function(tokens):
    """
    Expose a method for transforming tokens into the path function.

    """
    def transform(obj):
        path = ''
        obj = obj or {}

        for key in tokens:
            if isinstance(key, basestring):
                path += key
                continue

            regexp = re.compile('^%s$' % key['pattern'])

            value = obj.get(key['name'])
            if value is None:
                if key["optional"]:
                    continue
                else:
                    raise KeyError(
                        'Expected "{name}" to be defined'.format(**key)
                    )

            if isinstance(value, list):
                if not key['repeat']:
                    raise TypeError(
                        'Expected "{name}" to not repeat'.format(**key)
                    )

                if len(value) == 0:
                    if key['optional']:
                        continue
                    else:
                        raise ValueError(
                            'Expected "{name}" to not be empty'.format(**key)
                        )

                for i, val in enumerate(value):
                    val = unicode(val)
                    if not regexp.search(val):
                        raise ValueError(
                            'Expected all "{name}" to match "{pattern}"'.format(**key)
                        )

                    path += key['prefix'] if i == 0 else key['delimiter']
                    path += urllib.quote(val, '')

                continue

            value = unicode(value)
            if not regexp.search(value):
                raise ValueError(
                    'Expected "{name}" to match "{pattern}"'.format(**key)
                )

            path += key['prefix'] + urllib.quote(value.encode('utf8'), '-_.!~*\'()')

        return path

    return transform


def escape_string(string):
    return re.sub('([.+*?=^!:${}()[\\]|])', r'\\\1', string)


def escape_group(group):
    return re.sub('([=!:$()])', r'\\\1', group)


def flags(options):
    return 0 if options.get('sensitive') else re.I


def regexp_to_regexp(path, keys):
    match = path['source'].search(r'\((?!\?)')

    if match:
        keys.extend([
            {
                'name': i,
                'prefix': None,
                'delimiter': None,
                'optional': False,
                'repeat': False,
                'pattern': None
            }
            for i in range(len(match.groups()))
        ])

    return path


def array_to_regexp(paths, keys, options):
    parts = [
        path_to_regexp(path, keys, options).pattern
        for path in paths
    ]

    # TODO: options
    regexp = re.compile('(?:%s)' % ('|'.join(parts)))

    return regexp


def string_to_regexp(path, keys, options):
    tokens = parse(path)
    regexp = tokens_to_regexp(tokens, options)

    tokens = filter(lambda t: not isinstance(t, basestring), tokens)
    keys.extend(tokens)

    return regexp


def tokens_to_regexp(tokens, options=None):
    options = options or {}

    strict = options.get('strict')
    end = options.get('end') != False
    route = ''
    lastToken = tokens[-1]
    endsWithSlash = isinstance(lastToken, basestring) and lastToken.endswith('/')

    for token in tokens:
        if isinstance(token, basestring):
            route += escape_string(token)
            continue

        prefix = escape_string(token['prefix'])
        capture = token['pattern']

        if token['repeat']:
            capture += '(?:%s%s)*' % (prefix, capture)

        if token['optional']:
            if prefix:
                capture = '(?:%s(%s))?' % (prefix, capture)
            else:
                capture = '(%s)?' % capture
        else:
            capture = '%s(%s)' % (prefix, capture)

        route += capture

    if not strict:
        route = route[:-1] if endsWithSlash else route
        route += '(?:/(?=$))?'

    if end:
        route += '$'
    else:
        route += '' if strict and endsWithSlash else '(?=/|$)'

    return re.compile('^%s' % route, flags(options))


def path_to_regexp(path, keys=None, options=None):
    keys = keys if keys is not None else []
    options = options if options is not None else {}

    if isinstance(path, REGEXP_TYPE):
        return regexp_to_regexp(path, keys)

    if isinstance(path, list):
        return array_to_regexp(path, keys, options)

    return string_to_regexp(path, keys, options)
