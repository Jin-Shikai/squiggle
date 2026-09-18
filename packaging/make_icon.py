"""Draw the app icon and write packaging/Squiggle.icns.

    .venv/bin/python packaging/make_icon.py

The .icns is committed; rerun this only to change the design.
"""

import os
import subprocess
import tempfile

from AppKit import (
    NSBezierPath,
    NSBitmapImageRep,
    NSColor,
    NSDeviceRGBColorSpace,
    NSGradient,
    NSGraphicsContext,
    NSLineCapStyleRound,
    NSLineJoinStyleRound,
    NSPNGFileType,
)

HERE = os.path.dirname(os.path.abspath(__file__))
SIZES = [16, 32, 128, 256, 512]


def draw(size):
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(
        NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep))

    s = size / 1024.0
    # Apple's icon grid: an 824 pt rounded square centred on a 1024 canvas.
    tile = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        ((100 * s, 100 * s), (824 * s, 824 * s)), 185 * s, 185 * s)
    NSGradient.alloc().initWithStartingColor_endingColor_(
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.17, 0.18, 0.22, 1),
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.07, 0.07, 0.09, 1),
    ).drawInBezierPath_angle_(tile, -90)

    # The gesture trail: down, then right, with a loose wobble.
    trail = NSBezierPath.bezierPath()
    trail.setLineCapStyle_(NSLineCapStyleRound)
    trail.setLineJoinStyle_(NSLineJoinStyleRound)
    trail.moveToPoint_((300 * s, 730 * s))
    trail.curveToPoint_controlPoint1_controlPoint2_(
        (420 * s, 520 * s), (470 * s, 760 * s), (250 * s, 600 * s))
    trail.curveToPoint_controlPoint1_controlPoint2_(
        (560 * s, 400 * s), (560 * s, 460 * s), (420 * s, 330 * s))
    trail.curveToPoint_controlPoint1_controlPoint2_(
        (740 * s, 300 * s), (660 * s, 450 * s), (640 * s, 250 * s))
    trail.setLineWidth_(64 * s)
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.28, 0.56, 1.0, 1).set()
    trail.stroke()

    NSGraphicsContext.restoreGraphicsState()
    return rep.representationUsingType_properties_(NSPNGFileType, None)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "Squiggle.iconset")
        os.mkdir(iconset)
        for size in SIZES:
            for scale in (1, 2):
                name = "icon_%dx%d%s.png" % (size, size,
                                             "@2x" if scale == 2 else "")
                draw(size * scale).writeToFile_atomically_(
                    os.path.join(iconset, name), True)
        out = os.path.join(HERE, "Squiggle.icns")
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", out],
                       check=True)
        print(out)


if __name__ == "__main__":
    main()
