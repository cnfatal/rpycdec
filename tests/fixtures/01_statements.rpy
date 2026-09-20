# Scenario: basic statements, control flow and python blocks.
# Must stay valid for Ren'Py 7 and 8 alike (no python 3 only syntax).

define narrator = Character("Narrator", color="#fff")
define e = Character("Eileen")
default flag = True
default counter = 0
default items = ["a", "b"]

image bg room = Solid("#000")

style basic_red:
    size 40

label start:
    e "Hello, world."
    "A narration line."
    $ flag = False
    $ counter = counter + 1
    python:
        total = counter + 1
        doubled = total * 2

    if flag:
        "flag is set"
    elif counter:
        "counter is set"
    else:
        "neither"

    while counter > 0:
        $ counter = counter - 1
        if counter == 1:
            "almost done"
        else:
            pass

    menu andre_menu:
        "choice one":
            jump one
        "choice two" if flag:
            call two
        "choice three":
            pass

    scene bg room
    show e at left
    hide e
    with fade

    jump one

label one:
    "one"
    return

label two:
    "two"
    return
