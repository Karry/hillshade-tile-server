# Hillshade tile server

PHP+Python scripts for building simple server with hillshade tiles.
 
### Prapare DEM data

 - Download DEM data for requested region from SRTM site or other source, 
 for example [viewfinderpanoramas.org](viewfinderpanoramas.org)
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
gdalbuildvrt -input_file_list /data/dem/files.lst /data/dem/files.vrt
```
### Web server

 - copy this repository to web server rood dir, rename `config.php.example` 
 to `config.php` and setup paths for your server
 - prepare script for cleanup tile cache

```bash
TODO
``` 

## Third-party software

 - **Leaflet** - BSD-2-Clause (https://leafletjs.com/)
 - **Leaflet HASH plugin** - MIT (https://github.com/mlevans/leaflet-hash)

