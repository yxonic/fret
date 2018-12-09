import fret.util


def test_colored():
    # test colored output w/o bold font
    assert fret.util.colored('hello') == 'hello'
    assert fret.util.colored('hello', 'r') == \
        '\x1b[31mhello\x1b[0m'
    assert fret.util.colored('hello', 'r', 'b', style='b') == \
        '\x1b[1;31;44mhello\x1b[0m'
    assert fret.util.colored('hello', 'r', style='b') == \
        '\x1b[1;31mhello\x1b[0m'
