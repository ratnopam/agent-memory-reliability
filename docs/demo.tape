# docs/demo.gif — the two commands worth watching, in about forty seconds.
#
#   vhs docs/demo.tape
#
# This file is the reproducible part; the GIF is not. The author renders it from this tape,
# watches it, and commits it once it is worth showing — a recording nobody looked at is a
# claim nobody checked, and no gate here can tell a good frame from a bad one. Run it from
# the repository root with the package installed (`pip install -e ".[test]"`).
#
# If `vhs` prints "Creating docs/demo.gif..." and no file appears, its GIF encoder has
# failed silently against the installed ffmpeg — it was vhs 0.12.0 against ffmpeg's
# Lavc63 here. Frame capture is unaffected, so render the frames and assemble them:
#
#   sed 's|^Output docs/demo.gif|Output docs/frames/|' docs/demo.tape > /tmp/frames.tape
#   vhs /tmp/frames.tape
#   ffmpeg -y -framerate 45 -i 'docs/frames/frame-text-%05d.png' \
#       -vf "fps=12,scale=1500:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=64[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5" \
#       -loop 0 docs/demo.gif
#   rm -rf docs/frames
#
# 45 is the capture rate vhs used; keeping it makes the GIF play back in real time.
#
# Sized for a tablet standing on a table at a conference: 24pt type, dark background, no
# window chrome, and nothing on screen that a reader has to squint at. The demo prints
# fifteen lines on purpose — they all have to fit.

Output docs/demo.gif
# Output docs/frames/

Set Shell zsh
Set FontSize 24
Set Width 1500
Set Height 800
Set Padding 28
Set Theme "Builtin Dark"
Set TypingSpeed 45ms
Set PlaybackSpeed 1.0

# vhs runs a non-interactive shell, so an interactive PROMPT that calls a function the
# rc file never defined is emitted literally — every frame reads `$(build_prompt)`,
# including the last one. The prompt is set here so the recording does not depend on
# whose machine it was rendered on.
Hide
Type "PROMPT='$ '" Enter
Type "clear" Enter
Show

# `amr demo` runs the whole suite in-process before it prints anything, which is about
# eight and a half seconds on the machine this was last rendered on. The wait has to cover
# that run *and* leave the matrix on screen long enough to read fifteen lines; at six
# seconds the screen was cleared while the suite was still working and the GIF showed the
# command producing nothing at all.
Type "amr demo"
Sleep 600ms
Enter
Sleep 15s

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
