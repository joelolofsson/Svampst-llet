#!/bin/bash
# Copy to files dir in the app using AssetManager on first launch or we can just copy them manually for now?
# Wait, "Copy this file into the app's assets or raw resources during build"
# Let's put it in assets.

mkdir -p /home/joel/projectArea/hittaSkogClone/SvampRadar/app/src/main/assets
cp /home/joel/projectArea/hittaSkogClone/geodata/opentopomap_ale_lilla_edet.mbtiles /home/joel/projectArea/hittaSkogClone/SvampRadar/app/src/main/assets/
