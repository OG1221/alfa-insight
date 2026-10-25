#!/usr/bin/env python3
"""Start the local contest app once and keep it alive after the launcher exits."""
import argparse,json,os,subprocess,sys,time,urllib.request,urllib.error,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8000'

def health():
    try:
        with urllib.request.urlopen(BASE+'/api/health',timeout=2) as r:return json.load(r).get('database')=='postgresql'
    except (OSError,ValueError):return False

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','status'],nargs='?',default='start');p.add_argument('--open',action='store_true');a=p.parse_args()
    if a.action=='status':
        print('Альфа Инсайт доступен: '+BASE if health() else 'Сервер не запущен');return 0 if health() else 1
    if not health():
        runtime=ROOT/'runtime';runtime.mkdir(exist_ok=True)
        # The foreground script checks PostgreSQL, migrations and builds the UI.
        with (runtime/'server.log').open('ab') as log:
            proc=subprocess.Popen([str(ROOT/'scripts/start-local.sh')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        (runtime/'server.pid').write_text(str(proc.pid)+'\n')
        for _ in range(60):
            if health():break
            if proc.poll() is not None:
                print('Ошибка запуска. Подробности: '+str(runtime/'server.log'));return 1
            time.sleep(1)
        else:
            print('Запуск продолжается. Журнал: '+str(runtime/'server.log'));return 1
    print('Альфа Инсайт: '+BASE)
    if a.open:webbrowser.open(BASE)
    return 0
if __name__=='__main__':raise SystemExit(main())
