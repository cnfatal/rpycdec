# Scenario: the translate statement, in all of its forms.
# min-renpy: 7.6.3

define e = Character("Eileen")
default counter = 0

style translated_style:
    size 20

label start:
    e "hello"
    return

translate french strings:
    old "hello"
    new "bonjour"
    old "A line with {b}tags{/b} and \"quotes\"."
    new "Une ligne avec des {b}balises{/b} et des \"guillemets\"."

translate french python:
    counter = 1
    config.name = "Le Jeu"

translate french style translated_style:
    size 30
    color "#f00"

translate french start:
    e "bonjour"
    $ counter = 2

translate french start_second:
    e "au revoir"
