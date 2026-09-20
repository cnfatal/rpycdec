# Scenario: the old testcase framework (clauses, no selectors).
# min-renpy: 7.6.3
# max-renpy: 8.4.1
# Ren'Py 8.5 replaced this grammar, so the fixture cannot compile there.

testcase clauses:
    scroll "Bar" until "Player Experience"
    click until "Yes."
    click
    click button 4
    click button 4 pos (10, 20) always
    "Quoted pattern."
    type PAGEDOWN
    type "Tom"
    type "\n"
    move (0, 0) pattern "Bar"
    drag [(0, 0), (100, 100)] button 2 pattern "Bar" steps 5
    pause .5
    run Start()
    $ flag = True

    python:
        flag = False
        other = 1

    "Implicit click."

testcase control_flow:
    if click:
        click
    assert flag
    jump other
    call helper

testcase helper:
    click

testcase other:
    label start
    click until label start
