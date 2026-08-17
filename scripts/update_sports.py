#!/usr/bin/env python3
from __future__ import annotations
import copy,json,re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
DATA_FILE=ROOT/'data'/'sports-data.json'
TZ=ZoneInfo('Europe/Berlin'); NOW=datetime.now(TZ)
SESSION=requests.Session(); SESSION.headers.update({'User-Agent':'Mozilla/5.0 (compatible; LokalsportSchwerinDashboard/2.0)','Accept-Language':'de-DE,de;q=0.9'})
CFG:dict[str,dict[str,Any]]={
'ssc_damen':{'kind':'ssc','team':'SSC Palmberg Schwerin','schedule':'https://www.schweriner-sc.com/spielplan/','table':'https://www.volleyball-bundesliga.de/cms/home/1_bundesliga_frauen/statistik/hauptrunde.xhtml'},
'ssc_herren':{'kind':'volley','team':'Schweriner SC','schedule':'https://www.volley.de/halle/erg/qp/orga-1/saison-2026/bereich-1000/wid-12731/wsid-0//mode-s/','table':'https://www.volley.de/halle/erg/qp/orga-1/saison-2026/bereich-1000/wid-12731/wsid-0/'},
'pampow_frauen_volleyball':{'kind':'volley','team':'MSV Pampow','schedule':'https://www.volley.de/halle/erg/qp/orga-1/saison-2026/bereich-1000/wid-12730/wsid-0//mode-s/','table':'https://www.volley.de/halle/erg/qp/orga-1/saison-2026/bereich-1000/wid-12730/wsid-0/'},
'fcm_schwerin':{'kind':'football','team':'FC Mecklenburg Schwerin','url':'https://www.fussball.de/mannschaft/fc-mecklenburg-schwerin-fc-mecklenburg-schwerin-mecklenburg-vorpommern/-/saison/2627/team-id/01HEF5JJVO000000VV0AG80NVTE4NR7G'},
'msv_pampow':{'kind':'football','team':'MSV Pampow','url':'https://www.fussball.de/mannschaft/msv-pampow-msv-pampow-mecklenburg-vorpommern/-/saison/2627/team-id/011MI9OV30000000VTVG0001VTR8C1K7'},
'dynamo_schwerin':{'kind':'football','team':'SG Dynamo Schwerin','url':'https://www.fussball.de/mannschaft/sg-dynamo-schwerin-sg-dynamo-schwerin-ev-mecklenburg-vorpommern/-/saison/2627/team-id/011MIB2D60000000VTVG0001VTR8C1K7'},
'mecklenburger_stiere':{'kind':'handball','team':'Mecklenburger Stiere Schwerin','schedule':'https://www.handball.net/mannschaften/nuliga.oos.1776634/spielplan?dateFrom=2026-07-01&dateTo=2027-06-30','table':'https://www.handball.net/mannschaften/nuliga.oos.1776634/tabelle'}}

def clean(s:str)->str:return re.sub(r'\s+',' ',(s or '').replace('\xa0',' ')).strip()
def norm(s:str)->str:return re.sub(r'[^a-z0-9äöüß]+',' ',clean(s).lower().replace('(h)','')).strip()
def fetch(url:str)->BeautifulSoup:
 r=SESSION.get(url,timeout=30);r.raise_for_status();return BeautifulSoup(r.text,'html.parser')
def de_dt(ds:str,ts:str|None=None)->datetime:
 d=None
 for f in ('%d.%m.%Y','%d.%m.%y'):
  try:d=datetime.strptime(ds.strip(),f);break
  except ValueError:pass
 if d is None:raise ValueError(ds)
 if ts:
  h,m=map(int,ts.split(':'));d=d.replace(hour=h,minute=m)
 return d.replace(tzinfo=TZ)
def short_dt(ddmm:str,hhmm:str)->datetime:
 day,month=map(int,ddmm.strip('.').split('.'));year=2026 if month>=7 else 2027;h,m=map(int,hhmm.split(':'));return datetime(year,month,day,h,m,tzinfo=TZ)
def iso(d):return d.isoformat() if d else None
def fmt_game(d,o):return f'{d:%d.%m.%Y} · {d:%H:%M} · vs {o}'
def table_rank(soup,team):
 nt=norm(team)
 for tr in soup.find_all('tr'):
  cells=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
  if not cells or nt not in norm(' '.join(cells)):continue
  for c in cells[:3]:
   m=re.fullmatch(r'(\d{1,2})\.?',c)
   if m:return m.group(1)
 return None

def parse_volley(cfg):
 team=cfg['team'];soup=fetch(cfg['schedule']);games=[]
 for tr in soup.find_all('tr'):
  cells=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
  if len(cells)<5 or not re.fullmatch(r'\d{2}\.\d{2}\.\d{2}',cells[0]) or not re.fullmatch(r'\d{1,2}:\d{2}',cells[1]):continue
  a,b=cells[3],cells[4]
  if norm(team) not in {norm(a),norm(b)}:continue
  dt=de_dt(cells[0],cells[1]);ah,bh='(h)' in a.lower(),'(h)' in b.lower();a0=re.sub(r'\s*\(H\)\s*','',a,flags=re.I);b0=re.sub(r'\s*\(H\)\s*','',b,flags=re.I)
  result=''
  for c in cells[5:]:
   m=re.search(r'\b([0-3])\s*:\s*([0-3])\b',c)
   if m:result=m.group(1)+':'+m.group(2);break
  ia=norm(team)==norm(a0);games.append({'dt':dt,'home':ah if ia else bh,'opp':b0 if ia else a0,'result':result})
 if not games:raise RuntimeError('keine Spielzeilen gefunden')
 out={};r=table_rank(fetch(cfg['table']),team)
 if r:out['rank']=r+('=' if r=='1' and not any(g['result'] for g in games) else '')
 done=[g for g in games if g['dt']<=NOW and g['result']]
 if done:
  g=max(done,key=lambda x:x['dt']);out.update(lastResult=f"{'vs' if g['home'] else 'bei'} {g['opp']} · {g['result']}",lastGameAt=iso(g['dt']))
 elif min(g['dt'] for g in games)>NOW:out.update(lastResult='Noch kein Saisonspiel',lastGameAt=None)
 homes=[g for g in games if g['dt']>NOW and g['home']]
 if homes:
  g=min(homes,key=lambda x:x['dt']);out.update(nextHomeAt=iso(g['dt']),nextHomeOpponent=f"vs {g['opp']}",nextHomeGame=fmt_game(g['dt'],g['opp']))
 return out

def dedupe(s):
 s=clean(s);p=s.split();return ' '.join(p[:len(p)//2]) if len(p)%2==0 and p[:len(p)//2]==p[len(p)//2:] else s
def parse_ssc(cfg):
 team=cfg['team'];soup=fetch(cfg['schedule']);games=[]
 for tr in soup.find_all('tr'):
  cells=[clean(x.get_text(' ',strip=True)) for x in tr.find_all(['th','td'])]
  if len(cells)<4:continue
  m=re.search(r'(\d{2}\.\d{2}\.\d{4}).*?(\d{1,2}:\d{2})',cells[0])
  if not m:continue
  home,away=dedupe(cells[2]),dedupe(cells[3])
  if norm(team) not in {norm(home),norm(away)}:continue
  dt=de_dt(m.group(1),m.group(2));ih=norm(team)==norm(home);opp=away if ih else home;result=''
  if len(cells)>4:
   sm=re.search(r'\b([0-3])\s*:\s*([0-3])\b',cells[4]);result=sm.group(0).replace(' ','') if sm else ''
  games.append({'dt':dt,'home':ih,'opp':opp,'result':result})
 if not games:raise RuntimeError('SSC-Spielplan nicht lesbar')
 out={}
 try:
  r=table_rank(fetch(cfg['table']),team)
  if r:out['rank']=r
 except Exception:pass
 done=[g for g in games if g['dt']<=NOW and g['result']]
 if done:
  g=max(done,key=lambda x:x['dt']);out.update(lastResult=f"{'vs' if g['home'] else 'bei'} {g['opp']} · {g['result']}",lastGameAt=iso(g['dt']))
 elif min(g['dt'] for g in games)>NOW:out.update(lastResult='Noch kein Saisonspiel',lastGameAt=None)
 homes=[g for g in games if g['dt']>NOW and g['home']]
 if homes:
  g=min(homes,key=lambda x:x['dt']);out.update(nextHomeAt=iso(g['dt']),nextHomeOpponent=f"vs {g['opp']}",nextHomeGame=fmt_game(g['dt'],g['opp']))
 return out

def parse_football(cfg):
 team=cfg['team'];soup=fetch(cfg['url']);text=clean(soup.get_text(' ',strip=True));out={};m=re.search(r'\b(\d{1,2})\s+Tabellenplatz\b',text,re.I)
 if m:out['rank']=m.group(1)
 games=[]
 for tr in soup.find_all('tr'):
  row=clean(tr.get_text(' ',strip=True));dm=re.search(r'(\d{2}\.\d{2}\.\d{4})',row);tm=re.search(r'\b(\d{1,2}:\d{2})\b',row)
  if not dm or not tm or norm(team) not in norm(row):continue
  names=[]
  for a in tr.find_all('a'):
   if '/mannschaft/' in a.get('href',''):
    t=clean(a.get_text(' ',strip=True))
    if t and t not in names:names.append(t)
  teams=names[-2:]
  if len(teams)!=2 or norm(team) not in {norm(teams[0]),norm(teams[1])}:continue
  dt=de_dt(dm.group(1),tm.group(1));ih=norm(team)==norm(teams[0]);opp=teams[1] if ih else teams[0];after=row[row.find(tm.group(1))+len(tm.group(1)):];sm=re.search(r'\b(\d{1,2})\s*:\s*(\d{1,2})\b',after);score=sm.group(1)+':'+sm.group(2) if sm else ''
  games.append({'dt':dt,'home':ih,'opp':opp,'score':score})
 homes=[g for g in games if g['dt']>NOW and g['home']]
 if homes:
  g=min(homes,key=lambda x:x['dt']);out.update(nextHomeAt=iso(g['dt']),nextHomeOpponent=f"vs {g['opp']}",nextHomeGame=fmt_game(g['dt'],g['opp']))
 done=[g for g in games if g['dt']<=NOW and g['score']]
 if done:
  g=max(done,key=lambda x:x['dt']);out.update(lastResult=f"{'vs' if g['home'] else 'bei'} {g['opp']} · {g['score']}",lastGameAt=iso(g['dt']))
 if not m and not games:raise RuntimeError('FUSSBALL.DE-Struktur nicht erkannt')
 return out

def parse_handball(cfg):
 team=cfg['team'];soup=fetch(cfg['schedule']);games=[]
 for a in soup.find_all('a'):
  t=clean(a.get_text(' ',strip=True))
  if norm(team) not in norm(t):continue
  dm=re.search(r'\b(\d{1,2}\.\d{1,2}\.)',t);tm=re.search(r'(\d{1,2}:\d{2})\s*Uhr',t)
  if not dm or not tm:continue
  dt=short_dt(dm.group(1),tm.group(1));body=t[dm.end():];pos=body.find(tm.group(1));home=clean(body[:pos]);away=clean(body[pos+len(tm.group(1)):].replace('Uhr','',1));home=re.sub(r'^(?:Mo|Di|Mi|Do|Fr|Sa|So)[,.]?\s*','',home)
  if not home or not away:continue
  ih=norm(team)==norm(home);games.append({'dt':dt,'home':ih,'opp':away if ih else home})
 games=list({(g['dt'],norm(g['opp']),g['home']):g for g in games}.values())
 if not games:raise RuntimeError('handball.net-Spielkarten nicht erkannt')
 out={}
 try:
  r=table_rank(fetch(cfg['table']),team)
  if r:out['rank']=r
 except Exception:pass
 homes=[g for g in games if g['dt']>NOW and g['home']]
 if homes:
  g=min(homes,key=lambda x:x['dt']);out.update(nextHomeAt=iso(g['dt']),nextHomeOpponent=f"vs {g['opp']}",nextHomeGame=fmt_game(g['dt'],g['opp']))
 if min(g['dt'] for g in games)>NOW:out.update(lastResult='Noch kein Saisonspiel',lastGameAt=None)
 return out

def update_one(previous):
 club=copy.deepcopy(previous);cfg=CFG.get(club['id'])
 if not cfg:return club
 try:
  changes={'volley':parse_volley,'ssc':parse_ssc,'football':parse_football,'handball':parse_handball}[cfg['kind']](cfg);club.update({k:v for k,v in changes.items() if v is not None or k=='lastGameAt'});club['dataUpdatedAt']=NOW.isoformat();club['sourceStatus']='ok';club['error']=None
 except Exception as e:club['sourceStatus']='stale';club['error']=f'{type(e).__name__}: {e}'
 return club

def main():
 base=json.loads(DATA_FILE.read_text(encoding='utf-8'));clubs=[update_one(c) for c in base.get('clubs',[])];payload={'season':'2026/27','updatedAt':NOW.isoformat(),'note':'Automatisch aktualisiert. Bei Parserfehlern bleiben die letzten guten Werte erhalten und die Kachel wird als älter markiert.','clubs':clubs};DATA_FILE.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 for c in clubs:print(f"{c['id']}: {c.get('sourceStatus')} {c.get('error') or ''}")
if __name__=='__main__':main()
