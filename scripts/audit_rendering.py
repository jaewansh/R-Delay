"""Raster diagnostics, not a human visual review. Never call this visual approval."""
from pathlib import Path
import json, re
import fitz
from PIL import Image, ImageStat
ROOT=Path(__file__).resolve().parents[1]
results=[]
for name in ('RDelay_참가신청서_v0.1','RDelay_종합설계서_v0.1'):
    path=ROOT/'deliverables'/(name+'.pdf')
    pdf=fitz.open(path)
    for i,p in enumerate(pdf):
        spans=[s for b in p.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l.get('spans',[])]
        nums=[s for s in spans if re.fullmatch(r'\s*\(\d+\)\s*',s['text'])]
        data={'document':name,'page':i+1,'images':len(p.get_images()),'drawing_objects':len(p.get_drawings()),'equation_regions':[]}
        for s in nums:
            x0,y0,x1,y1=s['bbox']
            # A narrow horizontal strip left of the equation number.
            clip=fitz.Rect(42,max(0,y0-11),max(44,x0-5),min(p.rect.height,y1+11))
            pix=p.get_pixmap(matrix=fitz.Matrix(2,2),clip=clip,alpha=False)
            im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples).convert('L')
            hist=im.histogram();ink=sum(hist[:180])/max(1,sum(hist))
            data['equation_regions'].append({'label':s['text'].strip(),'number_bbox':list(s['bbox']),'crop':list(clip),'dark_pixel_fraction':ink,'nonempty_ink':ink>0.001})
        results.append(data)
path=ROOT/'artifacts/rendered_equation_diagnostics.json'
path.write_text(json.dumps(results,ensure_ascii=False,indent=2))
print(path.read_text())
