"""Recover sprite regions, fit replacement arrows, and export a Sparrow atlas."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage


def load(path):
    return Image.open(path).convert("RGBA")


def detect(args):
    source = Path(args.sheet).resolve()
    sheet = load(source)
    alpha = np.asarray(sheet)[..., 3]
    labels, count = ndimage.label(alpha > args.alpha, structure=np.ones((3, 3)))
    regions = []
    for component, slices in enumerate(ndimage.find_objects(labels), 1):
        if slices is None:
            continue
        ys, xs = slices
        area = int(np.count_nonzero(labels[ys, xs] == component))
        if area < args.min_area:
            continue
        x, y, w, h = xs.start, ys.start, xs.stop-xs.start, ys.stop-ys.start
        regions.append(dict(box=[x, y, w, h], replace=min(w, h) >= 70 and .55 < w/h < 1.8))
    regions.sort(key=lambda r: (r['box'][1] // 30, r['box'][0]))
    for i, region in enumerate(regions):
        region.update(name=f"sprite_{i:03d}", source="auto", rotation="auto", flip="auto", recolor="target")
    artwork = [str(Path(name).resolve()) for name in args.source]
    recipe = dict(version=1, sheet=str(source), sources=artwork,
                  sources_of_truth=dict(layout=str(source), artwork=artwork,
                                        overrides="This recipe; edit boxes, names, and transforms here.",
                                        unknown="Original animation names, frame offsets, and timing are not recoverable from pixels."),
                  regions=regions)
    path = Path(args.recipe)
    if path.exists():
        raise ValueError(f"Recipe already exists: {path}. Choose another --recipe to detect again.")
    path.write_text(json.dumps(recipe, indent=2) + '\n')
    preview(sheet, regions).save(path.with_suffix('.png'))
    print(f"Saved {path} and {path.with_suffix('.png')}: {len(regions)} regions, {sum(r['replace'] for r in regions)} arrow candidates.")


def preview(sheet, regions):
    result = sheet.copy()
    draw = ImageDraw.Draw(result)
    for i, r in enumerate(regions):
        x, y, w, h = r['box']
        color = '#ffff00' if r['replace'] else '#ff8800'
        draw.rectangle((x, y, x+w-1, y+h-1), outline=color, width=2)
        draw.text((x+3, y+3), str(i), fill='white', stroke_width=2, stroke_fill='black')
    return result


def trimmed(image):
    box = image.getchannel('A').getbbox()
    if box is None:
        raise ValueError('Arrow image is fully transparent.')
    return image.crop(box)


def mask(image):
    # A common comparison size makes the score independent of sprite resolution.
    return np.asarray(image.getchannel('A').resize((64, 64))) > 96


def fit(target, region, sources):
    target_mask = mask(target)
    best = None
    for name, source in sources.items():
        if region['source'] != 'auto' and region['source'] != name:
            continue
        rotations = [0, 90, 180, 270] if region['rotation'] == 'auto' else [float(region['rotation'])]
        flips = ['none', 'horizontal', 'vertical'] if region['flip'] == 'auto' else [region['flip']]
        for flip in flips:
            if flip not in ('none', 'horizontal', 'vertical'):
                raise ValueError(f'Unknown flip: {flip}')
            base = ImageOps.mirror(source) if flip == 'horizontal' else ImageOps.flip(source) if flip == 'vertical' else source
            for rotation in rotations:
                candidate = trimmed(base.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC))
                candidate_mask = mask(candidate)
                union = np.count_nonzero(candidate_mask | target_mask)
                score = np.count_nonzero(candidate_mask & target_mask) / max(1, union)
                if best is None or score > best[0]:
                    best = score, candidate, dict(source=name, rotation=rotation, flip=flip, score=round(score, 4))
    if best is None:
        raise ValueError(f"No available source matches {region['source']!r}")
    _, candidate, report = best
    if 'body_box' in region:
        left, top, right, bottom = region['body_box']
        body_width, body_height = region['body_size']
        if not (0 <= left < right <= candidate.width and 0 <= top < bottom <= candidate.height) or min(body_width, body_height) <= 0:
            raise ValueError(f"Invalid body bounds for {region['name']}")
        scale_x, scale_y = body_width / (right-left), body_height / (bottom-top)
        size = (round(candidate.width*scale_x), round(candidate.height*scale_y))
        center_x, center_y = region.get('body_center', (target.width/2, target.height/2))
        if not (body_width/2 <= center_x <= target.width-body_width/2 and
                body_height/2 <= center_y <= target.height-body_height/2):
            raise ValueError(f"Arrow body center falls outside region {region['name']}")
        position = (round(center_x-body_width/2-left*scale_x),
                    round(center_y-body_height/2-top*scale_y))
        if body_width > target.width or body_height > target.height:
            raise ValueError(f"Arrow body does not fit inside region {region['name']}")
        canvas = Image.new('RGBA', target.size)
        # shortcut: outer glow clips at existing atlas bounds; repack if wider halos are needed.
        canvas.alpha_composite(candidate.resize(size, Image.Resampling.LANCZOS), position)
        candidate = canvas
    else:
        candidate = candidate.resize(target.size, Image.Resampling.LANCZOS)
    recolor = region.get('recolor', 'target')
    if recolor != 'none':
        # Remove source hue before applying a layout state's color and brightness.
        gray = np.asarray(ImageOps.grayscale(candidate), dtype=np.float32)
        hsv = np.zeros((*gray.shape, 3), dtype=np.uint8)
        if recolor == 'target':
            target_hsv = np.array(target.convert('RGB').convert('HSV'))
            opaque = np.asarray(target)[..., 3] > 96
            distance = ndimage.distance_transform_edt(opaque)
            interior = opaque & (distance >= max(1, distance.max() * .35))
            valid = interior & (target_hsv[..., 1] > 40)
            if valid.any():
                # Circular hue mean avoids the discontinuity at red.
                angles = target_hsv[..., 0][valid] * (2*np.pi/256)
                hue = int((np.angle(np.exp(1j*angles).mean()) % (2*np.pi))*256/(2*np.pi)) % 256
            else:
                hue = 0
            samples = target_hsv[valid if valid.any() else opaque]
            if not len(samples):
                raise ValueError('Target region is fully transparent.')
            saturation = float(np.median(samples[:, 1]))
            brightness = float(np.percentile(samples[:, 2], 80))
        else:
            hue, saturation, brightness = Image.new('RGB', (1, 1), recolor).convert('HSV').getpixel((0, 0))
        source_visible = np.asarray(candidate)[..., 3] > 96
        reference = max(1, float(np.percentile(gray[source_visible], 95))) if source_visible.any() else 255
        hsv[..., 0] = hue
        hsv[..., 1] = round(saturation)
        hsv[..., 2] = np.clip(gray / reference * brightness, 0, 255).astype(np.uint8)
        report['target_color'] = dict(hue=int(hue), saturation=round(saturation), brightness=round(brightness))
        colored = Image.fromarray(hsv, 'HSV').convert('RGBA')
        colored.putalpha(candidate.getchannel('A'))
        candidate = colored
    if 'trail_body' in region:
        body = sources[region.get('trail_profile', region['trail_body'])]
        profile = body.crop((0, body.height//2, body.width, body.height//2+1))
        profile = np.asarray(profile.resize((target.width, 1), Image.Resampling.LANCZOS))[0]
        pixels = np.array(candidate)
        if region['source'] == region['trail_body']:
            pixels[:] = profile
        depth = min(8, target.height//2)
        for offset in range(depth):
            weight = offset / depth
            pixels[offset] = np.rint(profile*(1-weight) + pixels[offset]*weight).astype(np.uint8)
        candidate = Image.fromarray(pixels)
    return candidate, report


def construct(args):
    recipe_path = Path(args.recipe).resolve()
    recipe = json.loads(recipe_path.read_text())
    def resolve(value):
        path = Path(value)
        return path if path.is_absolute() else recipe_path.parent / path
    sheet = load(resolve(recipe['sheet']))
    sources = {name: trimmed(load(resolve(name))) for name in recipe['sources'] if resolve(name).exists()}
    if not sources and any(r['replace'] for r in recipe['regions']):
        raise ValueError('No source arrows found. Check source paths in the recipe.')
    output = Path(args.output)
    if output.suffix.lower() != '.png':
        raise ValueError('--output must end in .png')
    if output.resolve() in {resolve(recipe['sheet']).resolve(), *(resolve(n).resolve() for n in recipe['sources'])}:
        raise ValueError('Output must not overwrite a source image.')
    output.parent.mkdir(parents=True, exist_ok=True)
    result = sheet.copy()
    report = []
    atlas = ET.Element('TextureAtlas', imagePath=output.name)
    names = set()
    for region in recipe['regions']:
        x, y, w, h = region['box']
        if any(type(v) is not int for v in (x, y, w, h)) or min(x, y) < 0 or min(w, h) <= 0 or x+w > sheet.width or y+h > sheet.height:
            raise ValueError(f"Invalid region box: {region['box']}")
        if region['name'] in names:
            raise ValueError(f"Duplicate frame name: {region['name']}")
        names.add(region['name'])
        if region['replace']:
            replacement, match = fit(sheet.crop((x, y, x+w, y+h)), region, sources)
            result.paste((0, 0, 0, 0), (x, y, x+w, y+h))
            result.alpha_composite(replacement, (x, y))
            report.append(dict(name=region['name'], **match))
        attrs = dict(name=region['name'], x=str(x), y=str(y), width=str(w), height=str(h))
        for key in ('frameX', 'frameY', 'frameWidth', 'frameHeight'):
            if key in region:
                attrs[key] = str(region[key])
        ET.SubElement(atlas, 'SubTexture', attrs)
    result.save(output)
    ET.indent(atlas)
    ET.ElementTree(atlas).write(output.with_suffix('.xml'), encoding='utf-8', xml_declaration=True)
    output.with_suffix('.matches.json').write_text(json.dumps(report, indent=2)+'\n')
    preview(result, recipe['regions']).save(output.with_suffix('.preview.png'))
    overlay = Image.blend(sheet, result, .5)
    overlay.save(output.with_suffix('.overlay.png'))
    print(f"Saved {output}, XML, numbered preview, 50% overlay, and match scores. Review XML names before engine use.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    detect_parser = commands.add_parser('detect', help='Recover connected sprite bounds into an editable recipe.')
    detect_parser.add_argument('--sheet', required=True)
    detect_parser.add_argument('--source', action='append', required=True, help='Replacement artwork; repeat for multiple images.')
    detect_parser.add_argument('--recipe', required=True)
    detect_parser.add_argument('--alpha', type=int, default=0)
    detect_parser.add_argument('--min-area', type=int, default=100)
    detect_parser.set_defaults(run=detect)
    build_parser = commands.add_parser('build', help='Fit arrow artwork and export the new sheet and XML.')
    build_parser.add_argument('--recipe', required=True)
    build_parser.add_argument('--output', required=True)
    build_parser.set_defaults(run=construct)
    args = parser.parse_args()
    try:
        args.run(args)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Error: {error}\n')


if __name__ == '__main__':
    main()
