# Scenario: ATL, every statement the transform language has.
# min-renpy: 7.6.3

image logo = Solid("#f00")

init python:
    def myfunc(trans, st, at):
        return None

    def mywarp(trans, st, at):
        return 1.0

transform interpolation:
    xalign 0.5
    linear 1.0 zoom 1.5
    ease 0.5 alpha 0.0
    easein 0.5 xpos 0.0
    easeout 0.5 xpos 1.0
    warp mywarp 1.0 xpos 0.5
    linear 1.0 xpos 0.25
    pause 0.5
    time 1.0

transform grouping:
    block:
        xpos 0.1
        xpos 0.2
    repeat 2
    block:
        linear 0.5 ypos 0.1
    repeat

transform branching:
    parallel:
        linear 1.0 xpos 0.5
    parallel:
        linear 1.0 ypos 0.5
    choice:
        linear 0.1 alpha 1.0
        linear 0.1 alpha 0.0
    choice 0.5:
        linear 0.1 alpha 0.0

transform handling:
    on show:
        alpha 0.0
        linear 0.5 alpha 1.0
    on hide:
        linear 0.5 alpha 0.0
    on show, hide:
        xpos 0.0
    function myfunc
    event ending

transform children:
    contains:
        "logo"
        xalign 0
    contains:
        Text("hi")
    contains "logo"

transform revolutions:
    xalign 0.0 yalign 0.0
    linear 1.0 xalign 1.0 yalign 1.0
    linear 1.0 xpos 0.0 counterclockwise
    linear 1.0 xpos 0.5 clockwise circles 2
    linear 1.0 xanchor 1.0 knot 0.5 knot 1.0

transform animated:
    animation
    "logo"
    xalign 0.0
    linear 5.0 xalign 1.0
    repeat

label start:
    show logo at interpolation
    show logo at branching with dissolve
    hide logo
    return
