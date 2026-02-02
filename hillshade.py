#!/usr/bin/python3
# Inspired by https://alastaira.wordpress.com/2011/07/20/creating-hill-shaded-tile-overlays/
# from Alastair Aitchison
# BSD 3-Clause License
#
# Copyright (c) 2018, Lukáš Karas
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys
import os
from osgeo import gdal
from PIL import Image as PImage, ImageFilter, ImageOps

if (len(sys.argv) < 5):
    print("Too few arguments!\n"
          "Usage: \n"
          "  %s input.tif output.png z x y" % (sys.argv[0]))

    print("\nInput should contains DEM data in GDAL compatible format"
          "\nOutput is png file.")
    exit(1)

infile = sys.argv[1]
outfile = sys.argv[2]
tmpFile1 = outfile + "1.tif"
tmpFile2 = outfile + "2.tif"

# z/x/y are tile indices; keep them as ints for correct clamping & comparisons.
z = int(sys.argv[3])
x = int(sys.argv[4])
y = int(sys.argv[5])

#################################################################
# rendering bounding box

# XYZ tiles are defined in WebMercator (EPSG:3857). To avoid tiny latitude-
# dependent shifts caused by doing bounds in EPSG:4326 and letting GDAL round
# during reprojection, compute bounds directly in EPSG:3857 meters.
WEBMERCATOR_HALF_WORLD = 20037508.342789244


def tile_bounds_3857(zv: float, xv: float, yv: float):
    """Return (minx, miny, maxx, maxy) bounds for an XYZ tile in EPSG:3857."""
    n = 2.0 ** zv
    tile_size = (2.0 * WEBMERCATOR_HALF_WORLD) / n
    minx = -WEBMERCATOR_HALF_WORLD + xv * tile_size
    maxx = minx + tile_size
    maxy = WEBMERCATOR_HALF_WORLD - yv * tile_size
    miny = maxy - tile_size
    return minx, miny, maxx, maxy


# Render with a 1-tile buffer around the requested tile for smoother
# hillshade/blur at edges, then crop back to 256x256.
worldRes = 2 ** z

bx1 = max(0, x - 1)
by1 = max(0, y - 1)
bx2 = min(worldRes - 1, x + 1)
by2 = min(worldRes - 1, y + 1)

minx1, miny1, maxx1, maxy1 = tile_bounds_3857(z, bx1, by1)
minx2, miny2, maxx2, maxy2 = tile_bounds_3857(z, bx2, by2)

# Combine bounds (note Y direction)
mercMinX = min(minx1, minx2)
mercMinY = min(miny1, miny2)
mercMaxX = max(maxx1, maxx2)
mercMaxY = max(maxy1, maxy2)

#################################################################
# tile sizes
size = 256, 256
renderWidth = 256
renderHeight = 256

cropX1 = 0
cropY1 = 0
if x > 0:
    cropX1 = 256
    renderWidth += 256
if y > 0:
    cropY1 = 256
    renderHeight += 256

cropX2 = renderWidth
cropY2 = renderHeight
if x < worldRes - 1:
    renderWidth += 256
    cropX2 = renderWidth - 256
if y < worldRes - 1:
    renderHeight += 256
    cropY2 = renderHeight - 256


#################################################################
# GDAL api: https://gdal.org/python/

print("GDAL Warp %s -> %s ([EPSG:3857] %.3f %.3f %.3f %.3f)" % (infile, tmpFile1, mercMinX, mercMinY, mercMaxX, mercMaxY))
print("Render hillshades to %d x %d, crop %d x %d, %d x %d" % (renderWidth, renderHeight, cropX1, cropY1, cropX2, cropY2))
print()

gdal.UseExceptions()
ds = gdal.Open(infile, gdal.GA_ReadOnly)

# Cut and transform to WebMercator (meters). Using bounds directly in EPSG:3857
# avoids rounding differences during reprojection. targetAlignedPixels=True
# snaps the output geotransform to the requested grid.
ds = gdal.Warp(
    tmpFile1,
    ds,
    options=gdal.WarpOptions(
        dstSRS="EPSG:3857",
        resampleAlg="cubic",
        outputBounds=[mercMinX, mercMinY, mercMaxX, mercMaxY],
        width=renderWidth,
        height=renderHeight,
        # GDAL requires -tr when -tap (targetAlignedPixels) is used.
        # Provide explicit resolution derived from bounds and target size.
        xRes=(mercMaxX - mercMinX) / float(renderWidth),
        yRes=(mercMaxY - mercMinY) / float(renderHeight),
        targetAlignedPixels=True,
        # If your DEM has nodata, you may want to propagate it:
        # dstNodata=0,
    ),
)

print(gdal.Info(ds))

alg = "ZevenbergenThorne"
if z < 11:
    alg = "Horn"

# In EPSG:3857 the horizontal unit is meters, so 'scale' should be 1.
# (The previous 111120 is only for degree-based DEMs.)
hs_ds = gdal.DEMProcessing(
    tmpFile2,
    ds,
    "hillshade",
    alg=alg,
    zFactor=2,
    scale=1,
    azimuth=315,
    combined=False,
    # multiDirectional=True,
)
hs_ds = None
ds = None

#################################################################
# process image

# Load the source file
src = PImage.open(tmpFile2)

# Convert to single channel
grey = ImageOps.grayscale(src)

# Make negative image
neg = ImageOps.invert(grey)

# Split channels
bands = neg.split()

# Create a new (black) image
black = PImage.new('RGBA', src.size)

# Copy inverted source into alpha channel of black image
black.putalpha(bands[0])

# Return a pixel access object that can be used to read and modify pixels
pixdata = black.load()

# Loop through image data
for y in range(black.size[1]):
    for x in range(black.size[0]):
        # Replace black pixels with pure transparent
        if pixdata[x, y] == (0, 0, 0, 255):
            pixdata[x, y] = (0, 0, 0, 0)
            # Lighten pixels slightly
        else:
            a = pixdata[x, y]
            pixdata[x, y] =  a[:-1] + (a[-1]-74,)

# Save as PNG
blurRadius = z - 10
if z>=17:
    blurRadius=blurRadius*1.5
if blurRadius > 1:
    black = black.filter(ImageFilter.GaussianBlur(radius=blurRadius))

# for experiments:
# .filter(ImageFilter.BoxBlur(15))
# .filter(ImageFilter.MedianFilter(size=3))
# .filter(ImageFilter.GaussianBlur(radius=10))

black \
    .crop((cropX1, cropY1, cropX2, cropY2)) \
    .resize(size, PImage.LANCZOS) \
    .save(outfile, "png")

os.remove(tmpFile1)
os.remove(tmpFile2)
