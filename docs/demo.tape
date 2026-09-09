# docs/demo.gif — the two commands worth watching, in about forty seconds.
#
#   vhs docs/demo.tape
#
# The GIF is not committed. A recording nobody generated from this tape is a claim nobody
# checked, and this file is the reproducible part. Run it from the repository root with the
# package installed (`pip install -e ".[test]"`).
#
# Sized for a tablet standing on a table at a conference: 24pt type, dark background, no
# window chrome, and nothing on screen that a reader has to squint at. The demo prints
# fifteen lines on purpose — they all have to fit.

Output docs/demo.gif

Set Shell zsh
Set FontSize 24
Set Width 1500
Set Height 800
Set Padding 28
Set Theme "Builtin Dark"
Set TypingSpeed 45ms
Set PlaybackSpeed 1.0

Hide
Type "clear" Enter
Show

Type "amr demo"
Sleep 600ms
Enter
Sleep 6s

# Each command gets the whole screen; fifteen lines plus six will not both fit at 24pt.
Type "clear"
Enter
Sleep 400ms

Type "python examples/erasure_inflation.py"
Sleep 600ms
Enter
Sleep 7s

# The last frame is the one people photograph, so it holds on the three numbers.
Sleep 4s
