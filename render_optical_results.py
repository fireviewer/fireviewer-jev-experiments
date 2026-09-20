"""Visualize existing CPU branch outputs; never generate a new perimeter."""
import argparse,json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import rasterize
from rasterio.warp import transform_geom
from PIL import Image,ImageDraw,ImageFont

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);root=p.parse_args().root
base=root/'acquisition/sentinel2-analysis/2025-08-07';result=json.loads((base/'result.json').read_text())
font=ImageFont.load_default(size=16)
for pair in result['pairs']:
    panels=[];dataset=None
    for f in pair['files']:
        with rasterio.open(base/f['path']) as src:
            # Three channels of the actual corrected reflectance archive.
            arr=src.read([4,2,1]);descriptions=src.descriptions
            assert descriptions[0]=='B04_20m' and descriptions[1]=='B8A_20m' and descriptions[3]=='B12_20m'
            rgb=np.moveaxis(np.nan_to_num(arr,nan=0),0,-1)
            rgb=(np.clip(rgb/0.5,0,1)**0.65*255).astype('uint8')
            rgb[~np.all(np.isfinite(arr),axis=0)]=[17,23,31]
            panels.append(Image.fromarray(rgb))
            shape=(src.height,src.width);transform=src.transform;crs=src.crs
    features=[(transform_geom('EPSG:4326',crs,pair['coverage_geojson']),1)]
    features.extend((transform_geom('EPSG:4326',crs,o['geometry_geojson']),2) for o in pair['observations'])
    mask=rasterize(features,out_shape=shape,transform=transform,dtype='uint8',fill=0)
    colors=np.array([[17,23,31],[163,178,192],[248,132,55]],dtype='uint8')
    panels.append(Image.fromarray(colors[mask]))
    canvas=Image.new('RGB',(1500,590),'#11171f');draw=ImageDraw.Draw(canvas)
    draw.text((20,12),pair['post_item_id']+' | effective resolution '+str(pair['resolution_m'])+' m',font=font,fill='white')
    labels=['4 Aug | SWIR / NIR / red','7 Aug | SWIR / NIR / red','Existing processor observations']
    for i,im in enumerate(panels):
        im.thumbnail((485,470));canvas.paste(im,(i*500+(500-im.width)//2,80))
        draw.text((i*500+12,52),labels[i],font=font,fill='white')
    draw.text((20,553),'Grey: valid coverage | Orange: modelled optical change | Dark: no admissible observation',font=font,fill='white')
    draw.text((20,575),'False-colour views. Not an active flame front, calibrated burn severity or final incident perimeter.',font=font,fill='#efc897')
    path=base/(pair['source_revision_sha256'][:24]+'-preview.png');canvas.save(path)
    print(path.name)
