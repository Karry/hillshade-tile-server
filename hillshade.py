#!/usr/bin/python3
# Inspired by https://alastaira.wordpress.com/2011/07/20/creating-hill-shaded-tile-overlays/
# from Alastair Aitchison

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

def tiley2lat(y, worldRes):
    n = math.pi - 2.0 * math.pi * y / worldRes
    return 180.0 / math.pi * math.atan(0.5 * (math.exp(n) - math.exp(-1*n)))

def tilex2lon(x,worldRes):
    return x / worldRes * 360.0 - 180

worldRes = pow(2.0, z)
lonRes = 360.0 / worldRes
lon1 = tilex2lon(max(0, x-1), worldRes)
lat1 = tiley2lat(max(0, y-1), worldRes)
lat2 = tiley2lat(min(worldRes-1, y+2), worldRes)
lon2 = tilex2lon(min(worldRes-1, x+2), worldRes)

latMin = min(lat1, lat2)
lonMin = min(lon1, lon2)
latMax = max(lat1, lat2)
lonMax = max(lon1, lon2)

#################################################################
# GDAL api: https://gdal.org/python/

ds = gdal.Open(infile, gdal.GA_ReadOnly)
# cut and transform to Merkaartor projection

ds = gdal.Warp(tmpFile1, ds,
               dstSRS = "EPSG:3857",
               resampleAlg = "cubic",
               outputBounds = [lonMin, latMin, lonMax, latMax],
               outputBoundsSRS = "EPSG:4326",
               width = 1024, height = 1024,
               options = ["TILED=YES"]
               )

print(gdal.Info(ds))

alg = "ZevenbergenThorne"
if z < 11:
    alg = "Horn"

ds = gdal.DEMProcessing(tmpFile2, ds, "hillshade",
                        alg = alg,
                        zFactor = 2,
                        #scale = 10,
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
size = 256, 256

cropX = src.size[0] / 3
cropY = src.size[1] / 3

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
    .crop( (cropX,cropY, src.size[0]-cropX, src.size[1]-cropY) ) \
    .resize(size, PImage.LANCZOS) \
    .save(outfile, "png")

os.remove(tmpFile1)
os.remove(tmpFile2)
