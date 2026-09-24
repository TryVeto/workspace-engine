"""Shallow, on-demand browsing inside the existing permitted roots."""
import os, uuid, time
from pathlib import Path

def children(catalog, path='', offset=0):
    if not path:
        roots=[{'id':'dir:'+str(p),'path':str(p),'name':p.name,'kind':'folder'} for p in catalog.roots]
        return {'children':roots,'total':len(roots),'offset':0,'hasMore':False}
    folder=catalog.permitted(path)
    if not folder.is_dir():raise ValueError('Folder is unavailable')
    offset=max(0,int(offset));entries=[];warnings=[]
    try:
        with os.scandir(folder) as scan:
            for e in scan:
                if e.name.startswith('.') or e.is_symlink():continue
                try:entries.append((not e.is_dir(follow_symlinks=False),e.name.casefold(),e))
                except OSError as ex:warnings.append(str(ex))
    except OSError as ex:raise ValueError('Cannot read this folder: '+str(ex))
    entries.sort(key=lambda e:(e[0],e[1]));out=[];stamp=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    root=next(r for r in catalog.roots if folder.is_relative_to(r))
    with catalog.connect() as c:
        for isfile,_,entry in entries[offset:offset+250]:
            p=Path(entry.path)
            try:st=entry.stat(follow_symlinks=False)
            except OSError as ex:warnings.append(str(ex));continue
            if not isfile:
                out.append({'id':'dir:'+str(p),'path':str(p),'name':p.name,'kind':'folder','modified':st.st_mtime});continue
            if not entry.is_file(follow_symlinks=False):continue
            old=c.execute('SELECT id FROM inventory WHERE path=?',(str(p),)).fetchone()
            fid=old['id'] if old else str(uuid.uuid4())
            c.execute('INSERT OR REPLACE INTO inventory VALUES(?,?,?,?,?,?,?,?,?)',(fid,str(p),str(root),st.st_dev,st.st_ino,st.st_size,st.st_mtime,stamp,'available'))
            out.append({'id':fid,'path':str(p),'name':p.name,'kind':'file','size':st.st_size,'modified':st.st_mtime,'status':'available'})
    return {'children':out,'path':str(folder),'total':len(entries),'offset':offset,'hasMore':offset+250<len(entries),'warnings':warnings}
