# Scenario: python statements, init priorities and store targets.
# min-renpy: 7.6.3

define config.name = "Fixture"
define deeply.nested = 1
default persistent.volume = 0.5
default my_var = 1

init python:
    init_flag = True

init 5 python:
    ordered = 1

init -1 python:
    earlier = 1

init python in mystore:
    in_store = 2

python early:
    early_flag = True

python early hide:
    early_hidden = True

label start:
    $ flag = True

    python:
        flag = False

    python hide:
        hidden = 1

    python in mystore:
        in_store = 3

    return
