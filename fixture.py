import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent
n=400000
with (root/'rows.ndjson').open('wb') as out:
    digest=hashlib.sha256()
    for i in range(n):
        row={}
        for j,name in enumerate('abcd'):
            t=i+7*j
            row[name]=None if t%31==0 else ('' if t%17==0 else 'value-'+str(t%64))
        b=json.dumps(row,separators=(',',':')).encode()+b'\n'
        out.write(b);digest.update(b)
print(n,digest.hexdigest())
