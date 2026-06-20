# Changelog

All notable changes to `peppy_rescaler` are documented in this file.

## [2.2] - 2026-06-20

### Added

- Scale Gallery Engine `meters.txt` keys:
  - `font.size.italic`, `progress.font.size`, `volume.font.size`
  - `volume.fill.width`, `volume.fill.radius`
  - `volume.arc.width`, `progress.arc.width`
- Suffix heuristics for future keys: `font.size.*`, `*.font.size`, `*.width`, `*.radius`
- `python3 rescale_template.py --verify` self-check for key classification

### Notes

- `folderlayer.*` / `fanart.*` pos and dimension keys were already covered by v2.1
  suffix rules; no change needed there.

## [2.1] - 2026-05-31

### Changed

- Preserve linear meter bar-count semantics during rescaling:
  - `position.regular` is no longer scaled.
  - `position.overload` is no longer scaled.
- Preserve ticker semantic/timing values during rescaling:
  - `playinfo.ticker.speed` is no longer scaled.
  - `playinfo.ticker.space_between` is no longer scaled.
  - `playinfo.ticker.end_spaces` is no longer scaled.
- Updated script version marker to `v2.1`.
- Updated README classification and version notes for v2.1 behavior.

## [2.0] - 2026-05-31

### Added

- Initial standalone `rescale_template.py` published in `peppy_rescaler`.
- Version marker in script output: `v2.0`.
- Complete README covering:
  - purpose and scope,
  - requirements and install,
  - configuration and scaling model,
  - key classification behavior in v2.0,
  - usage workflow and troubleshooting.

### Notes

- v2.0 reflects baseline behavior before semantic-key protection updates discussed later.
