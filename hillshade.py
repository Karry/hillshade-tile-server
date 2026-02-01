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
import math
import os
from osgeo import gdal, gdalconst
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

z = float(sys.argv[3])
x = float(sys.argv[4])
y = float(sys.argv[5])

#################################################################
# rendering bounding box

def tiley2lat(y, worldRes):
    n = math.pi - 2.0 * math.pi * y / worldRes
    return 180.0 / math.pi * math.atan(0.5 * (math.exp(n) - math.exp(-1*n)))

def tilex2lon(x,worldRes):
    return x / worldRes * 360.0 - 180

worldRes = pow(2.0, z)
lonRes = 360.0 / worldRes
lon1 = tilex2lon(max(0, x-1), worldRes)
lat1 = tiley2lat(max(0, y-1), worldRes)
lat2 = tiley2lat(min(worldRes, y+2), worldRes)
lon2 = tilex2lon(min(worldRes, x+2), worldRes)

latMin = min(lat1, lat2)
lonMin = min(lon1, lon2)
latMax = max(lat1, lat2)
lonMax = max(lon1, lon2)

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
if x < worldRes-1:
    renderWidth += 256
    cropX2 = renderWidth - 256
if y < worldRes-1:
    renderHeight += 256
    cropY2 = renderHeight - 256


#################################################################
# GDAL api: https://gdal.org/python/

print("GDAL Warp %s -> %s ([lon lat] %f %f %f %f)" % (infile, tmpFile1, lonMin, latMin, lonMax, latMax))
print("Render hillshades to %d x %d, crop %d x %d, %d x %d" % (renderWidth, renderHeight, cropX1, cropY1, cropX2, cropY2))
print()

gdal.UseExceptions()
ds = gdal.Open(infile, gdal.GA_ReadOnly)
# cut and transform to Merkaartor projection

ds = gdal.Warp(tmpFile1, ds,
               options = gdal.WarpOptions(
                   dstSRS='EPSG:4326',
                   resampleAlg = "cubic",
                   outputBounds = [lonMin, latMin, lonMax, latMax],
                   outputBoundsSRS = "EPSG:4326",
                   width = renderWidth, height = renderHeight,
                   # TILED = True
               ),
               )

print(gdal.Info(ds))

alg = "ZevenbergenThorne"
if z < 11:
    alg = "Horn"

ds = gdal.DEMProcessing(tmpFile2, ds, "hillshade",
                        alg = alg,
                        zFactor = 2,
                        # Ratio of vertical units to horizontal units. If the horizontal unit of the source DEM is degrees
                        # (e.g Lat/Long WGS84 projection), you can use scale=111120 if the vertical units are meters
                        scale = 111120,
                        azimuth = 315,
                        combined = False,
                        #multiDirectional = True,
                        )
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
blurRadius = z-10
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
