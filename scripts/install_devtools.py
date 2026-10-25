"""Fetch official portable ARM64 tools into ignored runtime/tools; no global config."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request,json,re,hashlib,tarfile,zipfile,shutil,os
ROOT=Path(__file__).resolve().parents[1];DEST=ROOT/'runtime/tools';DEST.mkdir(parents=True,exist_ok=True);BIN=DEST/'bin';BIN.mkdir(exist_ok=True)
def read(url):
    req=urllib.request.Request(url,headers={'User-Agent':'AlfaInsight-build','Accept':'application/vnd.github+json' if 'api.github.com' in url else '*/*'})
    return urllib.request.urlopen(req,timeout=90)
def install(spec):
    repo,match,name=spec
    try:
        with read('https://api.github.com/repos/'+repo+'/releases/latest') as r:release=json.load(r)
        asset=next(a for a in release['assets'] if match(a['name']));filename=asset['name'];path=DEST/filename
        if not path.exists():
            print('Downloading',name,filename,flush=True)
            with read(asset['browser_download_url']) as r,path.open('wb') as out:shutil.copyfileobj(r,out)
        digest=hashlib.sha256(path.read_bytes()).hexdigest();expected=asset.get('digest')
        if expected and expected!='sha256:'+digest:raise ValueError('SHA256 mismatch')
        if filename.endswith('.tar.gz') or filename.endswith('.tgz'):
            unpack=DEST/name;unpack.mkdir(exist_ok=True)
            with tarfile.open(path) as archive:archive.extractall(unpack,filter='data')
            if name=='lima':
                for p in (unpack/'bin').iterdir():
                    target=BIN/p.name
                    if not target.exists():target.symlink_to(p)
            else:
                binary=next(p for p in unpack.rglob(name) if p.is_file());shutil.copy2(binary,BIN/name)
        elif filename.endswith('.zip'):
            unpack=DEST/name;unpack.mkdir(exist_ok=True)
            with zipfile.ZipFile(path) as archive:archive.extractall(unpack)
            binary=next(p for p in unpack.rglob(name) if p.is_file());shutil.copy2(binary,BIN/name)
        else:shutil.copy2(path,BIN/name)
        for p in BIN.iterdir():p.chmod(0o755)
        print('Installed',name,release['tag_name'],flush=True)
        return {'tool':name,'version':release['tag_name'],'url':asset['browser_download_url'],'sha256':digest,'github_digest_verified':bool(expected)}
    except Exception as e:
        print('Failed',name,str(e),flush=True);return {'tool':name,'error':str(e)}
specs=[('abiosoft/colima',lambda s:s=='colima-Darwin-arm64','colima'),('lima-vm/lima',lambda s:bool(re.fullmatch(r'lima-[0-9.]+-Darwin-arm64.tar.gz',s)),'lima'),('cli/cli',lambda s:s.endswith('_macOS_arm64.zip'),'gh'),('docker/compose',lambda s:s=='docker-compose-darwin-aarch64','docker-compose'),('cloudflare/cloudflared',lambda s:s=='cloudflared-darwin-arm64.tgz','cloudflared')]
with ThreadPoolExecutor(max_workers=5) as pool:results=list(pool.map(install,specs))
# Docker publishes the CLI bundle on its own official download host.
try:
    base='https://download.docker.com/mac/static/stable/aarch64/'
    with read(base) as r:listing=r.read().decode()
    names=re.findall(r'href="(docker-([0-9]+\.[0-9]+\.[0-9]+)\.tgz)"',listing)
    name,version=max(names,key=lambda p:tuple(map(int,p[1].split('.'))));path=DEST/name
    if not path.exists():
        with read(base+name) as r,path.open('wb') as out:shutil.copyfileobj(r,out)
    with tarfile.open(path) as archive:archive.extractall(DEST/'docker',filter='data')
    for p in (DEST/'docker/docker').iterdir():
        if p.is_file():shutil.copy2(p,BIN/p.name);(BIN/p.name).chmod(0o755)
    results.append({'tool':'docker','version':version,'url':base+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()});print('Installed docker',version,flush=True)
except Exception as e:results.append({'tool':'docker','error':str(e)});print('Failed docker',str(e),flush=True)
(DEST/'manifest.json').write_text(json.dumps(results,indent=2))
