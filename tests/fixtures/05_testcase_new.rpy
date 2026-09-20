# Scenario: the Ren'Py 8.5 testcase/testsuite framework.
# min-renpy: 8.5
# This grammar does not exist in earlier Ren'Py, so the fixture cannot
# compile there.

default flag = True
default counter = 0

testsuite example:
    description "Covers the statements of a testsuite."
    xfail False
    only False
    enabled True
    parameter language = ["french", None]
    parameter (level, speed) = [(1, 2), (3, 4)]

    setup:
        depth 1
        $ flag = True

    before testsuite:
        $ counter = 1

    before testcase:
        python hide:
            flag = False
            counter = 2

    after testcase:
        $ counter = 3

    after testsuite:
        $ counter = 4

    teardown:
        exit

    testcase statements:
        description "Every command."
        pass
        advance
        advance until screen "choice"
        advance until "text" timeout 1.5
        click
        click button 2
        click "start"
        click "start" raw
        click id "pref_btn"
        click screen "prefs" layer "screens"
        click "focused" focused
        click "positioned" pos (10, 20) always
        click "until" until not "gone"
        move "History" pos (0, 0)
        scroll
        scroll amount 2 "Bar"
        scroll "Bar" until screen "main_menu"
        type "Tom"
        keysym "K_RETURN"
        keysym "K_BACKSPACE" repeat 3
        keysym "K_TAB" until screen "menu"
        drag "from" to "to"
        drag id "item" button 2 steps 4 to id "slot"
        skip
        skip fast
        pause 0.5
        pause until "Return"
        pause 0.5 until screen "menu" timeout 3.0
        run Start()
        run MainMenu(confirm=False) until screen "main_menu"
        screenshot "shot.png"
        screenshot "shot.png" max_pixel_difference 10 crop (0, 0, 10, 10)
        $ flag = True

        python:
            flag = False
            counter = 5

        assert "Yes."
        assert eval flag
        assert label start
        assert not "video game"
        assert "a" timeout 2.0 xfail False
        assert "b" xfail True
        assert screen "menu" and "text" or not screen "other"

        if "Yes.":
            pass
        elif screen "choice":
            pass
        else:
            pass

        if eval flag:
            pass
        elif eval (counter > 1 and flag):
            pass

    testcase disabled_case:
        enabled False
        xfail True
        pass

    testcase only_case:
        only True
        pass

    testsuite inner:
        before testcase:
            $ flag = True

        testcase nested:
            pass

testcase standalone:
    pass
