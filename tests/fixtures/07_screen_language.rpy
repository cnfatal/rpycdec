# Scenario: screen language statements and displayables.
# min-renpy: 7.6.3

default counter = 0
default volume = 0.5
default items = ["a", "b", "c"]
default flag = True

transform slide:
    xoffset 0
    linear 1.0 xoffset 20

style pref_button:
    size 20

screen child_screen(label_text, times=1):
    text "[label_text]"

screen displayables(name, amount=0.5, *args, **kwargs):
    tag menu
    zorder 10
    modal True
    sensitive flag
    style_prefix "pref"
    predict False

    default local_counter = 0
    python:
        local_counter = 1

    frame:
        background Solid("#000")
        xsize 100
        vbox:
            spacing 4
            text "text" size 20
            textbutton "button" action Return() at slide
            imagebutton:
                idle Solid("#111")
                hover Solid("#222")
                action NullAction()
            label "a label"
            null height 10
            add Solid("#333")
            input value VariableInputValue("name")
            bar value VariableValue("amount", 1.0) xsize 200
            vbar value VariableValue("amount", 1.0) ysize 100

    grid 2 2:
        text "0"
        text "1"
        text "2"
        text "3"

    side "c b":
        area (0, 0, 100, 100)
        viewport:
            draggable True
            mousewheel True
            text "viewport"
        vbar value VariableValue("amount", 1.0)

    vpgrid:
        cols 2
        spacing 2
        for item in items:
            text "[item]"

    fixed:
        xysize (200, 200)
        if local_counter:
            text "if branch"
        elif flag:
            text "elif branch"
        else:
            text "else branch"

    window:
        style "pref_button"
        text "window"

    key "dismiss" action Return()
    timer 1.0 action Return() repeat True
    on "show" action NullAction()
    showif flag:
        text "showif"

    use child_screen("child", times=2)
    use child_screen("child") id "child_id"
    use expression "child_screen" pass
    transclude

    mousearea:
        hovered NullAction()
        area (0, 0, 50, 50)

    drag:
        drag_name "draggable"
        draggable True
        drag_raise True
        xpos 10
        ypos 10
        text "drag me"

    for i in range(3):
        if i == 1:
            continue
        text "[i]"

label start:
    call screen displayables("done")
    show screen displayables("shown")
    hide screen displayables
    return
