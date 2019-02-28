import fret.util


def test_configuration():
    C = fret.util.Configuration

    # similar constructor as dict
    conf = C([['x', 3], ['y', 4], ['z', 5]])

    # mimicking dict operation (but following insertion order)
    assert 'x' in conf
    assert list(conf._keys()) == list(conf)
    assert list(conf._values()) == [3, 4, 5]
    assert list(conf._items()) == [('x', 3), ('y', 4), ('z', 5)]
    assert conf._get('x') == 3
    assert conf['y'] == 4
    assert conf._get('foo') is None
    assert len(conf) == 3
    assert conf == C([['y', 4], ['z', 5], ['x', 3]])

    # object-like api
    conf = C([('section1', conf._dict()), ('section2', {'foo': 'bar'})])
    assert conf.section1.x == 3
    assert conf.section2.foo == 'bar'


def test_colored():
    # test colored output w/o bold font
    assert fret.util.colored('hello') == 'hello'
    assert fret.util.colored('hello', 'r') == \
        '\x1b[31mhello\x1b[0m'
    assert fret.util.colored('hello', 'r', 'b', style='b') == \
        '\x1b[1;31;44mhello\x1b[0m'
    assert fret.util.colored('hello', 'r', style='b') == \
        '\x1b[1;31mhello\x1b[0m'


def test_classproperty():
    class A:
        @fret.util.classproperty
        def name(cls):
            return 'A'

    class B(A):
        @fret.util.classproperty
        def name(cls):
            return 'B'

    class C(A):
        pass

    assert A.name == 'A'
    assert B.name == 'B'
    assert C.name == 'A'


def test_naming():
    to_camel = fret.util.to_camel
    to_snake = fret.util.to_snake

    assert to_camel(to_snake('Html5ParserSimple')) == 'Html5ParserSimple'
    assert to_snake(to_camel('funny_joke3')) == 'funny_joke3'
