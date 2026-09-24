"""Read original image references without modifying or executing them."""
import hashlib
import xml.etree.ElementTree as ET

IMAGE_TYPES={".png":"image/png",".jpg":"image/jpeg",".jpeg":"image/jpeg",
             ".webp":"image/webp",".gif":"image/gif",".svg":"image/svg+xml"}
MAX_IMAGE=32*1024*1024

def read_image(path):
    mime=IMAGE_TYPES.get(path.suffix.lower())
    if not mime: raise ValueError("Unsupported image format")
    if path.stat().st_size>MAX_IMAGE: raise ValueError("Image exceeds the 32 MB preview limit")
    with path.open("rb") as stream: raw=stream.read(MAX_IMAGE+1)
    if len(raw)>MAX_IMAGE: raise ValueError("Image exceeds the 32 MB preview limit")
    valid=False
    if mime=="image/png":valid=raw.startswith(b"\x89PNG\r\n\x1a\n")
    elif mime=="image/jpeg":valid=raw.startswith(b"\xff\xd8\xff")
    elif mime=="image/gif":valid=raw[:6] in (b"GIF87a",b"GIF89a")
    elif mime=="image/webp":valid=raw[:4]==b"RIFF" and raw[8:12]==b"WEBP"
    elif mime=="image/svg+xml":
        if len(raw)>2*1024*1024:raise ValueError("SVG exceeds the 2 MB preview limit")
        text=raw.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError("SVG document declarations are not supported")
        try:valid=ET.fromstring(text).tag in ("svg","{http://www.w3.org/2000/svg}svg")
        except ET.ParseError:pass
    if not valid:raise ValueError("The file is not a supported image")
    return raw,mime

def information(path,relative,key,source):
    raw,mime=read_image(path)
    return {"id":key,"kind":"image","name":path.name,"file":relative,
            "path":str(path),"source":source,"mime":mime,"bytes":len(raw),
            "sha256":hashlib.sha256(raw).hexdigest(),"editable":False}
