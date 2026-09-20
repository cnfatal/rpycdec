# Scenario: the `use ... as NAME` clause, added in Ren'Py 8.4.
# min-renpy: 8.4

screen child_screen(label_text):
    text "[label_text]"

screen using_alias():
    use child_screen("first") as first_screen
    use child_screen("second") id "second_id" as second_screen
    $ first_screen["label_text"] = "changed"
