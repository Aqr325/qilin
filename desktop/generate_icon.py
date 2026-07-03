#!/usr/bin/env python3
"""
Generate a simple icon for the desktop app.
Creates icon.png and icon.ico in the desktop/ directory.
"""
import struct
import zlib
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))


def create_png(width, height, color=(0, 188, 212)):
    """Create a simple PNG with a shield shape."""
    pixels = []

    for y in range(height):
        row = []
        for x in range(width):
            # Shield shape
            cx, cy = width / 2, height / 2
            dx = abs(x - cx) / (width / 2)
            dy = (y - cy) / (height / 2)

            # Simple shield outline
            in_shield = False
            if y < height * 0.15:
                in_shield = True  # top bar
            elif y < height * 0.85:
                # Pentagon shield
                rel_y = y / height
                half_w = (1 - rel_y * 0.3) * (width / 2)
                if abs(x - cx) <= half_w:
                    in_shield = True

            if in_shield:
                # Gradient fill
                r = max(0, min(255, int(color[0] + (y / height) * 30)))
                g = max(0, min(255, int(color[1] + (y / height) * 20)))
                b = max(0, min(255, int(color[2] + (y / height) * 15)))
                a = 255
            else:
                r, g, b, a = 0, 0, 0, 0

            pixels.extend([r, g, b, a])

    # PNG structure
    def make_chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack('>I', len(data)) + c + crc

    # IHDR
    header = b'\x00' * 4  # no compression
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # IDAT - raw pixel data
    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter byte
        start = y * width * 4
        raw += bytes(pixels[start:start + width * 4])

    idat = make_chunk(b'IDAT', zlib.compress(raw))

    # IEND
    iend = make_chunk(b'IEND', b'')

    return b'\x89PNG\r\n\x1a\n' + ihdr + idat + iend


def create_ico(png_data, sizes=None):
    """Wrap PNG in ICO format."""
    if sizes is None:
        sizes = [(256, 256)]

    count = len(sizes)
    header = struct.pack('<HHH', 0, 1, count)

    entries = b''
    for w, h in sizes:
        img_size = len(png_data)
        img_offset = 6 + 16 * count  # header + directory
        # Directory entry
        bmp_size = 0 if w == 256 else w
        bmp_size2 = 0 if h == 256 else h
        entries += struct.pack('<BBBBHHII',
                               bmp_size, bmp_size2, 0, 0, 1, 32, img_size, img_offset)

    return header + entries + png_data


if __name__ == '__main__':
    # Create icon.png (256x256)
    png_data = create_png(256, 256)
    png_path = os.path.join(OUTPUT_DIR, 'icon.png')
    with open(png_path, 'wb') as f:
        f.write(png_data)
    print(f'Created {png_path} ({len(png_data)} bytes)')

    # Create small icon for tray (32x32)
    tray_png = create_png(32, 32)
    tray_path = os.path.join(OUTPUT_DIR, 'icon_tray.png')
    with open(tray_path, 'wb') as f:
        f.write(tray_png)
    print(f'Created {tray_path}')

    # Create icon.ico
    ico_data = create_ico(png_data)
    ico_path = os.path.join(OUTPUT_DIR, 'icon.ico')
    with open(ico_path, 'wb') as f:
        f.write(ico_data)
    print(f'Created {ico_path} ({len(ico_data)} bytes)')

    print('\nIcons generated successfully!')
