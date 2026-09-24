"""Original local video references with bounded reads and byte ranges."""
import hashlib
import re

VIDEO_TYPES={".mp4":"video/mp4",".webm":"video/webm"}
MAX_VIDEO=64*1024*1024

def read_video(path):
    mime=VIDEO_TYPES.get(path.suffix.lower())
    if not mime:raise ValueError("Unsupported video format")
    if path.stat().st_size>MAX_VIDEO:raise ValueError("Video exceeds the 64 MB preview limit")
    with path.open("rb") as f:raw=f.read(MAX_VIDEO+1)
    if len(raw)>MAX_VIDEO:raise ValueError("Video exceeds the 64 MB preview limit")
    valid=(len(raw)>=12 and raw[4:8]==b"ftyp") if mime=="video/mp4" else raw.startswith(b"\x1a\x45\xdf\xa3")
    if not valid:raise ValueError("The file is not a supported video")
    return raw,mime

def information(path,relative,key,source):
    raw,mime=read_video(path)
    return {"id":key,"kind":"video","name":path.name,"file":relative,"path":str(path),
            "source":source,"mime":mime,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),"editable":False}

def byte_range(raw,request):
    headers={"Accept-Ranges":"bytes"}
    if not request:return 200,raw,headers
    match=re.fullmatch(r"bytes=(\d*)-(\d*)",request)
    def invalid():return 416,b"",{**headers,"Content-Range":f"bytes */{len(raw)}"}
    if not match or not any(match.groups()):return invalid()
    first,last=match.groups()
    if not first and int(last)==0:return invalid()
    start=int(first) if first else max(0,len(raw)-int(last))
    end=min(int(last),len(raw)-1) if first and last else len(raw)-1
    if start>end or start>=len(raw):return invalid()
    headers["Content-Range"]=f"bytes {start}-{end}/{len(raw)}"
    return 206,raw[start:end+1],headers
