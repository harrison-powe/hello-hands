# Printed objects

`Cube Pick and Place Objects.3mf` holds the manipulation targets for this project — the
object dataset #2 is built around, and the tray it gets dropped into. Kept here as
reproducibility evidence: the demonstrations and the success criterion both depend on
the exact object, and a 35 mm two-tone cube is not something you can specify in prose.

## Print settings

Sliced for a **Bambu Lab A1**. PLA, 0.2 mm layer height, 15% infill, **no supports**.

Print on the **textured PEI plate with no glue**. The two-tone colour change is what
makes the cube legible to the wrist camera against the plate and the tray, so it is worth
keeping. Clear the plate before starting — these are small parts and a leftover skirt or
purge blob will drag them.

## What exists, and what has been used

The file contains three cube sizes — **25 mm, 30 mm and 35 mm**, all two-tone red/white —
plus the tray.

Only the **35 mm** cube has been used in a dataset so far. Dataset #2 and every policy
evaluated against it use that size exclusively; the 25 mm and 30 mm cubes are printed but
untested. Whether a policy trained on the 35 mm cube generalises down to the smaller two
is an open question and an obvious next experiment, but it has not been run, and nothing
in this repository's results speaks to it.
