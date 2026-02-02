# Hillshade tile server

PHP+Python scripts for building simple server with hillshade tiles.
You can [try result here](https://osmscout.karry.cz/hillshade/).

![river relief](screenshot.png)

### Prepare DEM data

 - Download DEM data for requested region from SRTM site or other source, 
 for example [viewfinderpanoramas.org](http://viewfinderpanoramas.org)
 - Convert DEM data to GeoTif format with GDAL tool

```bash
find /data/dem/ -type f -name *.hgt | \
while read file ; do \
    gdal_translate -of GTiff "$file" "$file.tif" \
done
```

 - Build GDAL virtual data set from multiple files
```bash
find /data/dem/ -type f -name *.hgt.tif > /data/dem/files.lst
gdalbuildvrt -input_file_list /data/dem/files.lst /data/dem/full.vrt
```

 - Downscale data for low zoom (<= 7)

```bash
cd /data/dem

# Important notes for low-zoom rasters:
# - Use EPSG:3857 (meters) for a stable grid.
# - Use a fixed -tr and -tap so the pixels are aligned to the target grid.
# - If your DEM coverage isn't global (common), DON'T force global WebMercator
#   bounds with -te. It will fill huge areas with nodata and can make edge
#   behavior look like a “shift”. Prefer warping just the dataset extent.
# - For better edge behavior, consider -dstalpha or a proper nodata value.

# Pixel size at zoom z for WebMercator is:
#   40075016.6856 / (256 * 2^z)

# low-zoom-7: pixel size ~ 1222.992 m
PIX7=1222.992452

gdalwarp \
    -of GTiff \
    -dstnodata 0 \
    -t_srs "EPSG:3857" \
    -tr ${PIX7} ${PIX7} \
    -tap \
    -r "cubic" \
    -multi \
    -wo "NUM_THREADS=ALL_CPUS" \
    -co "TILED=YES" \
    -co "COMPRESS=DEFLATE" \
    -co "PREDICTOR=2" \
    "full.vrt" \
    "low-zoom-7.tif"

# low-zoom-4: pixel size ~ 9783.94 m
PIX4=9783.939615

gdalwarp \
    -of GTiff \
    -dstnodata 0 \
    -t_srs "EPSG:3857" \
    -tr ${PIX4} ${PIX4} \
    -tap \
    -r "cubic" \
    -multi \
    -wo "NUM_THREADS=ALL_CPUS" \
    -co "TILED=YES" \
    -co "COMPRESS=DEFLATE" \
    -co "PREDICTOR=2" \
    "full.vrt" \
    "low-zoom-4.tif"
```

### Web server

 - it is required web server with PHP support (apache2 for example), 
   memcached server with corresponding PHP module, python3 with gdal 
   and Imaging (PIL) module...
 - copy this repository to web server root dir, rename `config.php.example` 
   to `config.php` and setup paths and other properties for your server
 - prepare script for cleanup tile cache and add it to system cron

```bash
TODO
``` 

## Third-party software

 - **Leaflet** - BSD-2-Clause (https://leafletjs.com/)
 - **Leaflet HASH plugin** - MIT (https://github.com/mlevans/leaflet-hash)
