# Landing page previews

These small display assets support the landing page's fan interaction. They are
website previews, not a new splitter run or primary production deliverables.

- `idol-01.png` through `idol-04.png` are unchanged copies of the four transparent
  variants from the existing `reference-idol-final-e2e` run. Its manifest records
  primary and transparent visual passes. This example includes approved
  reconstruction, as stated in the page.
- `uneven-*`, `dense-*`, and `clipped-*` are display previews prepared from the
  corresponding tracked `case-*-output.png` contact sheets. The script uses the
  renderer's exact card geometry, removes preview labels and frames, and uses the
  existing presentation module to isolate the subject. These previews are smaller
  than production assets and do not establish a new transparency quality verdict.
- The page's **View source** and **Full result** links retain the original tracked
  images. No original showcase image or evaluation manifest was modified.

Rebuild the 20 contact-sheet previews from the repository root:

```powershell
python scripts/build_landing_previews.py
```

The four reviewed idol PNGs are checked in directly, so serving the landing page
does not require the ignored local run directories or a build step.
