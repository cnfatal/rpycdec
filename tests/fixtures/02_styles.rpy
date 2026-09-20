# Scenario: style statements and their clauses.
# `clear` used to crash the decompiler (issue #25), every clause here must
# survive a compile -> decompile -> compile round trip.

style big_red:
    size 40
    color "#f00"
    bold True

style named_font is big_red

style cleared is big_red clear

style clear_and_size is big_red:
    clear
    size 20

style taking:
    take big_red

style touch_only:
    variant "touch"
    size 30

style seriously_everything is big_red clear:
    take cleared
    del bold
    variant "touch"
    size 12
    color "#00f"
