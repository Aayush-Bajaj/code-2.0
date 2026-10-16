# Sample Video & Frame Data Conventions

This directory houses factory visual evidence (video clips and extracted evaluation frames) for Carbon Passport's computer vision and smoke analysis pipeline.

## Clip Naming Conventions
All sample demonstration videos located under `data/samples/clips/` must adhere to standard descriptive identifiers:

1. `generator_blacksmoke.mp4`:
   - High-definition clip of an operational diesel genset with visible dark exhaust plumes.
   - Evaluated by `backend/vision/smoke.py` to trigger heavy opacity (`score_0_10 > 6.0`) and `maintenance_flag = true`.
2. `generator_nosmoke.mp4`:
   - Operational diesel genset under normal load without visible exhaust smoke (`smoke.level = 'none'`, `maintenance_flag = false`).
3. `forklift.mp4`:
   - Material handling forklift in operation inside shopfloor or yard, showing nameplate, engine bay, and wheel motion.
4. `truck.mp4`:
   - Outbound logistics truck arriving or loading finished components at the dispatch bay.

## Extracted Frames Directory
When running `scripts/extract_frames.py <clip_path>`, extracted frames and sidecar metadata are saved to:
`data/samples/frames/<video_name>/`
- `<idx>.jpg`: Extracted high-resolution frame.
- `frames_metadata.json`: Contains frame count, timestamps, and Laplacian sharpness scores.
