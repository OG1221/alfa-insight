"""Package a committed release without source datasets, secrets or runtime state."""
from pathlib import Path
import subprocess,zipfile,hashlib,json
ROOT=Path(__file__).resolve().parents[1]

def main():
    status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    if status.strip():raise SystemExit('Commit reviewed source changes before creating the release package')
    files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    forbidden=[p for p in files if p and (p.startswith(('data/private/','runtime/','.venv/','frontend/node_modules/')) or Path(p).name=='.env' or (Path(p).name.startswith('.env.') and Path(p).name!='.env.example'))]
    if forbidden:raise SystemExit('Sensitive paths unexpectedly tracked; release refused')
    out=ROOT/'submission';out.mkdir(exist_ok=True)
    rev=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    archive=out/'alfa-insight-source.zip';bundle=out/'alfa-insight-history.bundle'
    subprocess.run(['git','archive','--format=zip','--prefix=alfa-insight/','HEAD','-o',str(archive)],cwd=ROOT,check=True)
    subprocess.run(['git','bundle','create',str(bundle),'--all'],cwd=ROOT,check=True)
    subprocess.run(['git','bundle','verify',str(bundle)],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    manifest={'commit':rev,'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [archive,bundle]},'includes_official_data':False,'includes_secrets':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest,indent=2))
if __name__=='__main__':main()
