# Scenario: screen language (SL2) and its signatures.

default selected = False
default volume = 0.5

transform gentle_slide:
    xoffset 0
    linear 1.0 xoffset 20

screen no_params():
    tag menu
    vbox:
        text "no params" size 30

screen one_param(name):
    text "[name]"

screen with_defaults(greeting, times=2, loudly=False):
    for i in range(times):
        text "[greeting]"

screen starred_args(one, *rest, **kwargs):
    text "[one]"

screen keywords_only():
    modal True
    style_prefix "pref"
    vbox:
        textbutton "Return" action Return() at gentle_slide
        textbutton "Toggle" action ToggleVariable("selected") sensitive not selected
        bar value StaticValue(volume, 1.0)
        key "dismiss" action Hide("keywords_only")
        timer 1.0 action Hide("keywords_only")
        null height 10
        if selected:
            text "selected"
        else:
            text "not selected"

screen parent_screen():
    use one_param("child")
    textbutton "close" action Hide("parent_screen")

label start:
    $ renpy.call_screen("no_params")
    call screen one_param("hi")
    show screen with_defaults("hey")
    hide screen with_defaults
    return
