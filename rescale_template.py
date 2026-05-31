#!/usr/bin/env python3
"""
PeppyMeter Template Rescaler
Rescales template artwork and meters.txt values to target resolution.
Uses best-fit scaling with centering for mismatched aspect ratios.
"""

import os
import re
import shutil
import sys
from pathlib import Path
from PIL import Image, ImageSequence

# =============================================================================
# CONFIGURATION
# =============================================================================

RESCALER_VERSION = "2.0"

SOURCE_WIDTH = 1920
SOURCE_HEIGHT = 1080
TARGET_WIDTH = 1280
TARGET_HEIGHT = 720

INPUT_FOLDER = "1920x1080_g5_713_CD"
OUTPUT_FOLDER = "1280x720_g5_713_CD"

# Raster types we resize; anything else is copied verbatim (fonts, svg, etc.)
RASTER_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}
GIF_EXTENSION = '.gif'

METERS_FILENAME = 'meters.txt'

# =============================================================================
# PARAMETER CLASSIFICATION
# =============================================================================

# Position keys: x,y on screen — scale + letterbox offset
POSITION_KEYS = {
    'left.origin.x', 'left.origin.y',
    'right.origin.x', 'right.origin.y',
    'left.x', 'left.y',
    'right.x', 'right.y',
    'meter.x', 'meter.y',
    'albumart.pos',
    'vinyl.pos', 'vinyl.center',
    'tonearm.pivot.screen',
    'tonearm.pos',
    'reel.left.pos', 'reel.left.center',
    'reel.right.pos', 'reel.right.center',
    'progress.pos',
    'volume.pos',
    'mute.pos',
    'playstate.pos',
    'repeat.pos',
    'shuffle.pos',
    'time.remaining.pos',
    'time.elapsed.pos',
    'time.total.pos',
    'playinfo.title.pos',
    'playinfo.artist.pos',
    'playinfo.album.pos',
    'playinfo.type.pos',
    'playinfo.samplerate.pos',
    'playinfo.ticker.pos',
    'playinfo.next.title.pos',
    'playinfo.next.artist.pos',
    'playinfo.next.album.pos',
}

# Dimension keys — scale only, no offset
DIMENSION_KEYS = {
    'distance',
    'position.regular', 'position.overload',
    'step.width.regular', 'step.width.overload',
    'albumart.dimension',
    'albumart.border',
    'vinyl.dimension',
    'progress.dim',
    'progress.head.offset',
    'progress.border',
    'volume.dim',
    'playinfo.type.dimension',
    'playinfo.title.maxwidth',
    'playinfo.artist.maxwidth',
    'playinfo.album.maxwidth',
    'playinfo.samplerate.maxwidth',
    'playinfo.ticker.maxwidth',
    'playinfo.next.title.maxwidth',
    'playinfo.next.artist.maxwidth',
    'playinfo.next.album.maxwidth',
    'playinfo.ticker.space_between',
    'playinfo.ticker.end_spaces',
    'playinfo.ticker.speed',
    'volume.slider.travel',
    'volume.slider.tip.offset',
    'tonearm.pivot.image',
    'mute.icon.glow',
    'playstate.icon.glow',
    'repeat.icon.glow',
    'shuffle.icon.glow',
}

# Font sizes — scale only
FONT_SIZE_KEYS = {
    'font.size.digi',
    'font.size.light',
    'font.size.regular',
    'font.size.bold',
    'time.remaining.fontsize',
    'time.elapsed.fontsize',
    'time.total.fontsize',
}

# Never treat as layout (explicit exclusions for heuristics)
KEYS_NEVER_SCALE = {
    'albumart.rotation.speed',
    'reel.rotation.speed',
    'ui.refresh.period',
    'steps.per.degree',
    'tonearm.drop.duration',
    'tonearm.lift.duration',
}


def classify_key(key: str):
    """
    Return 'position', 'dimension', 'font', or None.
    Unknown keys are classified with conservative suffix rules.
    """
    if key in KEYS_NEVER_SCALE:
        return None
    # Progress markers use 0–100 as percentage along the bar, not screen coords
    if re.match(r'^progress\.marker\.\d+\.pos$', key):
        return None
    if key in POSITION_KEYS:
        return 'position'
    if key in DIMENSION_KEYS:
        return 'dimension'
    if key in FONT_SIZE_KEYS:
        return 'font'

    if key.endswith('.pos'):
        return 'position'
    if key.endswith('.maxwidth'):
        return 'dimension'
    if key.endswith('.dimension'):
        return 'dimension'
    if '.fontsize' in key or key.endswith('.fontsize'):
        return 'font'
    if key.endswith('.offset'):
        return 'dimension'
    if key.endswith('.glow') and '.glow.' not in key:
        # e.g. mute.icon.glow; not *.glow.intensity / *.glow.color
        return 'dimension'
    if re.search(r'\.border$', key) and not key.endswith('.border.color'):
        return 'dimension'
    if key == 'playinfo.ticker.speed':
        return 'dimension'
    return None


# =============================================================================
# SCALING CALCULATOR
# =============================================================================

def calculate_scaling():
    """Calculate scale factor and centering offsets for best fit."""
    scale_x = TARGET_WIDTH / SOURCE_WIDTH
    scale_y = TARGET_HEIGHT / SOURCE_HEIGHT
    scale = min(scale_x, scale_y)

    scaled_w = int(SOURCE_WIDTH * scale)
    scaled_h = int(SOURCE_HEIGHT * scale)

    offset_x = (TARGET_WIDTH - scaled_w) // 2
    offset_y = (TARGET_HEIGHT - scaled_h) // 2

    return scale, offset_x, offset_y


# =============================================================================
# VALUE TRANSFORMERS
# =============================================================================

def scale_position_value(value_str, scale, offset_x, offset_y):
    """Scale position values (x,y or x,y,style)."""
    parts = value_str.split(',')
    result = []

    for i, part in enumerate(parts):
        part = part.strip()
        try:
            num = float(part)
            if i == 0:
                scaled = int(round(num * scale)) + offset_x
            elif i == 1:
                scaled = int(round(num * scale)) + offset_y
            else:
                scaled = int(round(num * scale))
            result.append(str(scaled))
        except ValueError:
            result.append(part)

    return ','.join(result)


def scale_dimension_value(value_str, scale):
    """Scale dimension values (w,h or comma-separated numbers)."""
    parts = value_str.split(',')
    result = []

    for part in parts:
        part = part.strip()
        try:
            num = float(part)
            scaled = int(round(num * scale))
            result.append(str(scaled))
        except ValueError:
            result.append(part)

    return ','.join(result)


def scale_font_size(value_str, scale):
    """Scale font size value."""
    try:
        num = float(value_str.strip())
        return str(int(round(num * scale)))
    except ValueError:
        return value_str


# =============================================================================
# METERS.TXT PARSER AND TRANSFORMER
# =============================================================================

def process_meters_txt(input_path, output_path, scale, offset_x, offset_y):
    """Parse and transform meters.txt with scaled values."""

    with open(input_path, 'r') as f:
        lines = f.readlines()

    output_lines = []
    warnings = []

    for line_num, line in enumerate(lines, 1):
        original = line.rstrip('\n\r')

        if not original.strip():
            output_lines.append(original)
            continue

        if original.strip().startswith('#'):
            output_lines.append(original)
            continue

        if original.strip().startswith('[') and original.strip().endswith(']'):
            output_lines.append(original)
            continue

        if '=' not in original:
            output_lines.append(original)
            continue

        eq_pos = original.index('=')
        key_part = original[:eq_pos].strip()
        value_part = original[eq_pos + 1:].strip()

        new_value = value_part
        kind = classify_key(key_part)

        if kind == 'position' and value_part:
            new_value = scale_position_value(value_part, scale, offset_x, offset_y)
        elif kind == 'dimension' and value_part:
            new_value = scale_dimension_value(value_part, scale)
        elif kind == 'font' and value_part:
            new_value = scale_font_size(value_part, scale)

        new_line = f"{key_part} = {new_value}"
        output_lines.append(new_line)

    with open(output_path, 'w') as f:
        for line in output_lines:
            f.write(line + '\n')

    return warnings


# =============================================================================
# IMAGE SAVE HELPERS
# =============================================================================

def _save_raster(img: Image.Image, dst_file: Path, ext: str):
    ext = ext.lower()
    dst_file.parent.mkdir(parents=True, exist_ok=True)
    if ext in ('.jpg', '.jpeg'):
        rgb = img.convert('RGB')
        rgb.save(dst_file, 'JPEG', quality=95)
    elif ext == '.webp':
        img.save(dst_file, 'WEBP', quality=90)
    elif ext == '.png':
        img.save(dst_file, 'PNG')
    elif ext in ('.bmp', '.tif', '.tiff'):
        img.save(dst_file)
    else:
        img.save(dst_file, 'PNG')


def _resize_gif(src_file: Path, dst_file: Path, scale: float) -> str:
    """Resize GIF (including multi-frame) using Pillow's frame iterator."""
    with Image.open(src_file) as im:
        frames = []
        durations = []
        for frame in ImageSequence.Iterator(im):
            rgba = frame.convert('RGBA')
            new_w = max(1, int(round(rgba.width * scale)))
            new_h = max(1, int(round(rgba.height * scale)))
            frames.append(rgba.resize((new_w, new_h), Image.LANCZOS))
            durations.append(frame.info.get('duration', im.info.get('duration', 100)))

        if not frames:
            shutil.copy2(src_file, dst_file)
            return "empty GIF (copied)"

        first = frames[0]
        orig_sz = im.size
        if len(frames) == 1:
            first.save(dst_file, 'GIF', save_all=False)
            return f"{orig_sz[0]}x{orig_sz[1]} -> {first.width}x{first.height}"

        first.save(
            dst_file,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=im.info.get('loop', 0),
            optimize=False,
        )
        return f"{orig_sz[0]}x{orig_sz[1]} -> {first.width}x{first.height} ({len(frames)} frames)"


# =============================================================================
# ASSET SYNC: resize rasters + copy everything else (fonts, etc.)
# =============================================================================

def sync_template_assets(input_folder, output_folder, scale):
    """
    Walk input template tree: resize raster images; copy all other files.
    Skips meters.txt (written separately from transformed content).
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder)

    processed = []
    copied = []
    errors = []

    for root, _dirs, files in os.walk(input_path):
        rel_root = Path(root).relative_to(input_path)
        target_dir = output_path / rel_root
        target_dir.mkdir(parents=True, exist_ok=True)

        for filename in files:
            if filename == METERS_FILENAME:
                continue

            src_file = Path(root) / filename
            dst_file = target_dir / filename
            ext = src_file.suffix.lower()

            try:
                if ext == GIF_EXTENSION:
                    msg = _resize_gif(src_file, dst_file, scale)
                    processed.append(f"{rel_root / filename}: {msg}")
                    continue

                if ext in RASTER_EXTENSIONS:
                    with Image.open(src_file) as img:
                        orig_w, orig_h = img.size
                        new_w = max(1, int(round(orig_w * scale)))
                        new_h = max(1, int(round(orig_h * scale)))
                        resized = img.resize((new_w, new_h), Image.LANCZOS)
                        _save_raster(resized, dst_file, ext)
                        processed.append(f"{rel_root / filename}: {orig_w}x{orig_h} -> {new_w}x{new_h}")
                    continue

                shutil.copy2(src_file, dst_file)
                copied.append(f"{rel_root / filename}")

            except Exception as e:
                errors.append(f"{rel_root / filename}: {str(e)}")

    return processed, copied, errors


# =============================================================================
# MAIN
# =============================================================================

def main():
    print(f"PeppyMeter Template Rescaler v{RESCALER_VERSION}")
    print("=" * 50)
    print(f"Source: {SOURCE_WIDTH}x{SOURCE_HEIGHT}")
    print(f"Target: {TARGET_WIDTH}x{TARGET_HEIGHT}")
    print(f"Input:  {INPUT_FOLDER}")
    print(f"Output: {OUTPUT_FOLDER}")
    print()

    if not os.path.isdir(INPUT_FOLDER):
        print(f"ERROR: Input folder not found: {INPUT_FOLDER}")
        sys.exit(1)

    meters_input = os.path.join(INPUT_FOLDER, METERS_FILENAME)
    if not os.path.isfile(meters_input):
        print(f"ERROR: {METERS_FILENAME} not found in {INPUT_FOLDER}")
        sys.exit(1)

    scale, offset_x, offset_y = calculate_scaling()
    print(f"Scale factor: {scale:.6f}")
    print(f"Centering offset: x={offset_x}, y={offset_y}")
    print()

    if os.path.exists(OUTPUT_FOLDER):
        shutil.rmtree(OUTPUT_FOLDER)
    os.makedirs(OUTPUT_FOLDER)

    print(f"Processing {METERS_FILENAME}...")
    meters_output = os.path.join(OUTPUT_FOLDER, METERS_FILENAME)
    warnings = process_meters_txt(meters_input, meters_output, scale, offset_x, offset_y)
    if warnings:
        for w in warnings:
            print(f"  WARNING: {w}")
    print("  Done.")
    print()

    print("Syncing assets (images + fonts + other files)...")
    processed, copied, errors = sync_template_assets(INPUT_FOLDER, OUTPUT_FOLDER, scale)
    for p in processed:
        print(f"  [img] {p}")
    for c in copied:
        print(f"  [cpy] {c}")
    if errors:
        print()
        print("Errors:")
        for e in errors:
            print(f"  ERROR: {e}")
    print()

    print("=" * 50)
    print(f"Complete. Output folder: {OUTPUT_FOLDER}")
    print(f"Images resized: {len(processed)}")
    print(f"Files copied:   {len(copied)}")
    if errors:
        print(f"Errors: {len(errors)}")


if __name__ == '__main__':
    main()
