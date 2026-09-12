from collections import deque
from pathlib import Path
import sys

from PIL import Image, ImageFilter


def remove_connected_background(source: Image.Image) -> Image.Image:
    image = source.convert("RGBA")
    width, height = image.size
    pixels = image.load()

    corner_samples = [
        pixels[x, y][:3]
        for x, y in (
            (0, 0),
            (width - 1, 0),
            (0, height - 1),
            (width - 1, height - 1),
        )
    ]
    key = tuple(sum(sample[channel] for sample in corner_samples) / 4 for channel in range(3))

    def is_background(x: int, y: int) -> bool:
        rgb = pixels[x, y][:3]
        distance = sum((rgb[channel] - key[channel]) ** 2 for channel in range(3)) ** 0.5
        return distance < 78

    background = set()
    queue = deque()
    for x in range(width):
        queue.extend(((x, 0), (x, height - 1)))
    for y in range(height):
        queue.extend(((0, y), (width - 1, y)))

    while queue:
        x, y = queue.popleft()
        if (x, y) in background or not is_background(x, y):
            continue
        background.add((x, y))
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    alpha = Image.new("L", image.size, 255)
    alpha_pixels = alpha.load()
    for x, y in background:
        alpha_pixels[x, y] = 0
    # Contract the matte by one source pixel to remove the pale screenshot halo,
    # then soften only the final antialiased edge.
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.35))
    image.putalpha(alpha)
    return image


def square_icon(cutout: Image.Image, size: int = 512) -> Image.Image:
    bbox = cutout.getbbox()
    if not bbox:
        raise RuntimeError("No foreground detected")
    cropped = cutout.crop(bbox)
    max_subject = int(size * 0.78)
    scale = min(max_subject / cropped.width, max_subject / cropped.height)
    resized = cropped.resize(
        (max(1, round(cropped.width * scale)), max(1, round(cropped.height * scale))),
        Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.alpha_composite(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: generate_favicons.py SOURCE_IMAGE PUBLIC_DIR")

    source_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    master = square_icon(remove_connected_background(Image.open(source_path)))
    master.save(output_dir / "mondaiy-mascot.png", optimize=True)

    for size in (16, 32, 48, 180, 192, 512):
        icon = master.resize((size, size), Image.Resampling.LANCZOS)
        name = "apple-touch-icon.png" if size == 180 else f"favicon-{size}x{size}.png"
        icon.save(output_dir / name, optimize=True)

    master.save(
        output_dir / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )


if __name__ == "__main__":
    main()
