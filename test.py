import json
import unittest

import nose.tools

import repath


def test_generator():
    with open('tests.json') as f:
        definitions = json.loads(f.read())

    for definition in definitions:
        yield check_definition, definition


def check_definition(definition):
    definition.extend([[]] * (5 - len(definition)))
    path, opts, tokens, matchCases, compileCases = definition
    regexp = repath.path_to_regexp(path, [], opts)

    if isinstance(path, basestring):
        nose.tools.eq_(repath.parse(path), tokens)

    compiled = repath.compile(path)
    for input_, output in compileCases:
        if output is not None:
            nose.tools.eq_(compiled(input_), output)
        else:
            with nose.tools.assert_raises(Exception):
                repath.compile(input_)

    for input_, output in matchCases:
        match = regexp.match(input_)
        if output is None:
            nose.tools.eq_(match, None)
        else:
            nose.tools.eq_(match.group(0), output[0])
            nose.tools.eq_(list(match.groups()), output[1:])


class Tests(unittest.TestCase):
    def setUp(self):
        self.path = '/user/:id'
        self.param = {
            'name': 'id',
            'prefix': '/',
            'delimiter': '/',
            'optional': False,
            'repeat': False,
            'pattern': '[^/]+?'
        }

    def check_regex_match(self, regexp, string, matched, *captures):
        match = regexp.match(string)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(0), matched)
        self.assertEqual(list(match.groups()), list(captures))

    def test_should_accept_array_of_keys_as_second_arg(self):
        keys = []
        regexp = repath.path_to_regexp(self.path, keys, {'end': False})

        # self.assertEqual(regexp.keys, keys)
        self.assertEqual(keys, [self.param])
        self.check_regex_match(regexp, '/user/123/show', '/user/123', '123')

    def test_should_work_with_keys_argument_as_none(self):
        regexp = repath.path_to_regexp(self.path, None, {'end': False})

        # self.assertEqual(regexp.keys, [self.param])
        self.check_regex_match(regexp, '/user/123/show', '/user/123', '123')

    def test_should_expose_method_to_compile_tokens_to_regexp(self):
        tokens = repath.parse(self.path)
        regexp = repath.tokens_to_regexp(tokens)

        self.check_regex_match(regexp, '/user/123', '/user/123', '123')

    def test_should_expose_method_to_compile_tokens_to_path_function(self):
        tokens = repath.parse(self.path)
        fn = repath.tokens_to_function(tokens)

        self.assertEqual(fn({'id': 123}), '/user/123')


class CompileErrorTests(unittest.TestCase):
    def check_to_path(self, path, params, exception, message):
        to_path = repath.compile(path)
        with self.assertRaises(exception) as context:
            to_path(params)

        self.assertEqual(context.exception.message, message)

    def test_should_raise_error_when_a_required_param_is_missing(self):
        self.check_to_path(
            '/a/:b/c', {},
            KeyError, 'Expected "b" to be defined')

    def test_should_raise_error_when_param_does_not_match_pattern(self):
        self.check_to_path(
            '/:foo(\\d+)', {'foo': 'abc'},
            ValueError, 'Expected "foo" to match "\\d+"')

    def test_should_raise_error_when_expecting_a_repeated_value(self):
        self.check_to_path(
            '/:foo+', {'foo': []},
            ValueError, 'Expected "foo" to not be empty')

    def test_should_raise_error_when_not_expecting_repeated_value(self):
        self.check_to_path(
            '/:foo', {'foo': []},
            TypeError, 'Expected "foo" to not repeat')

    def test_should_raise_error_when_repeated_value_does_not_match(self):
        self.check_to_path(
            '/:foo(\\d+)+', {'foo': [1, 2, 3, 'a']},
            ValueError, 'Expected all "foo" to match "\\d+"')
