"""Labeled native image batches with explicit, hash-bound OCR records."""
import hashlib
import json
import uuid
from dev_workspace import save_json

def attach_images(item,session,names,harness):
    if not isinstance(names,list) or not 1<=len(names)<=3 or len(set(names))!=len(names):raise ValueError('Choose1..3 distinct session image names')
    try:from PIL import Image,ImageOps,ImageDraw
    except ImportError as error:raise ValueError('Install requirements-browser.txt for labeled image batches') from error
    images=[];manifest=[]
    for name in names:
        if not isinstance(name,str) or name not in session.files:raise ValueError('Only downloaded session images are allowed')
        path=session.files[name].resolve()
        if not path.is_relative_to(session.directory.resolve()) or path.stat().st_size>2*1024*1024:raise ValueError('Image outside session or exceeds2MiB')
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
        with Image.open(path) as source:
            if source.format not in ('PNG','JPEG','WEBP') or source.width*source.height>12000000:raise ValueError('Use PNG/JPEG/WebP images up to12MP')
            image=ImageOps.exif_transpose(source).convert('RGB');image.thumbnail((1400,2000))
        label='IMAGE '+sha[:16]+' | '+name
        panel=Image.new('RGB',(max(700,image.width),image.height+54),'white')
        ImageDraw.Draw(panel).text((12,12),label,fill='black',font_size=22)
        panel.paste(image,(0,54));images.append(panel);manifest.append({'image_id':sha[:16],'name':name,'sha256':sha})
    if len({m['image_id'] for m in manifest})!=len(manifest):raise ValueError('Duplicate image bytes; attach one copy')
    batch=uuid.uuid4().hex;sheet=Image.new('RGB',(max(i.width for i in images),sum(i.height for i in images)), '#cccccc');top=0
    for image in images:sheet.paste(image,(0,top));top+=image.height
    target=session.directory/('image-batch-'+batch+'.png');sheet.save(target)
    if target.stat().st_size>8*1024*1024:target.unlink();raise ValueError('Labeled image batch exceeds8MiB; choose fewer images')
    # Persist before upload. A failed/uncertain upload is never silently repeated.
    item.setdefault('imageBatches',{})[batch]={'images':manifest,'status':'upload_pending'}
    save_json(session.directory/('image-batch-'+batch+'.json'),item['imageBatches'][batch])
    harness.upload(target)
    item['imageBatches'][batch]['status']='attached'
    return {'ok':True,'batch_id':batch,'images':manifest,'attachment':target.name,'note':'One native contact sheet with image_id visibly printed above each image. Read the label, never infer identity from attachment order. Return browser.record_images with every image_id exactly once; unknown values must be null.'}

def record_images(item,args,directory):
    batch=item.get('imageBatches',{}).get(args['batch_id'])
    if not batch or batch['status']!='attached':raise ValueError('Unknown or unattached image batch')
    records=args['records'];expected={i['image_id']:i for i in batch['images']}
    if not isinstance(records,list) or len(records)!=len(expected):raise ValueError('Return one record per image')
    seen=set();joined=[]
    for record in records:
        if not isinstance(record,dict) or set(record)!={'image_id','fields'} or record['image_id'] not in expected or record['image_id'] in seen:raise ValueError('Missing, duplicate or foreign image_id')
        if not isinstance(record['fields'],dict) or len(json.dumps(record,allow_nan=False).encode())>20000:raise ValueError('Invalid image fields')
        if any(not isinstance(v,(str,int,float,bool,type(None))) for v in record['fields'].values()):raise ValueError('OCR fields must be scalar or null')
        seen.add(record['image_id']);joined.append({**expected[record['image_id']],'fields':record['fields'],'provenance':'Copilot visual extraction; not independently verified'})
    result={'ok':True,'batch_id':args['batch_id'],'records':joined,'verified':False}
    save_json(directory/('ocr-'+args['batch_id']+'.json'),result)
    batch['records']=joined
    return result
