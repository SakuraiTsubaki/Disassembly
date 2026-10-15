#!/usr/bin/env python3
"""Locate and verify the Generation I link-synchronised BattleRandom routine."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=56

def candidate(data:bytes,o:int,random_address:int):
    if o+LENGTH>len(data):return None
    c=data[o:o+LENGTH];fixed={0:0xFA,3:0xFE,5:0xC2,8:0xE5,9:0xC5,10:0xFA,13:0x4F,14:0x06,15:0,16:0x21,19:0x09,20:0x3C,21:0xEA,24:0xFE,25:0x09,26:0x7E,27:0xC1,28:0xE1,29:0xD8,30:0xE5,31:0xC5,32:0xF5,33:0xAF,34:0xEA,37:0x21,40:0x06,41:0x09,42:0x7E,43:0x4F,44:0x87,45:0x87,46:0x81,47:0x3C,48:0x22,49:0x05,50:0x20,51:0xF6,52:0xF1,53:0xC1,54:0xE1,55:0xC9}
    if any(c[i]!=v for i,v in fixed.items()) or int.from_bytes(c[6:8],'little')!=random_address:return None
    if c[22:24]!=c[11:13] or c[35:37]!=c[11:13] or c[38:40]!=c[17:19]:return None
    bank=o//0x4000;address=o if bank==0 else 0x4000+o%0x4000
    if address+52+int.from_bytes(c[51:52],'little',signed=True)!=address+42:return None
    return {'rom_offset':o,'bank':bank,'address':address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(c).hexdigest(),'state':{'wLinkState':int.from_bytes(c[1:3],'little'),'link_state_battling':c[4],'wLinkBattleRandomNumberListIndex':int.from_bytes(c[11:13],'little'),'wLinkBattleRandomNumberList':int.from_bytes(c[17:19],'little'),'stream_length':10,'refreshed_seed_count':9},'control_flow':{'non_link_jump':{'bank':0,'address':random_address},'early_return_offset':29,'refresh_loop_offset':42,'refresh_loop_back_edge':{'from_offset':50,'to_offset':42}},'prng':{'formula':'seed = (seed * 5 + 1) mod 256','refreshed_seed_count':9}}

def locate(data:bytes,random_address:int):
    out=[];start=0;prefix=bytes((0xFA,))
    while True:
      o=data.find(prefix,start)
      if o<0:break
      f=candidate(data,o,random_address)
      if f:out.append(f)
      start=o+1
    return out

def ids(root):
 p=root/'research/releases.csv'
 if p.is_file():
  with p.open(encoding='utf-8',newline='') as h:return[r['id'] for r in csv.DictReader(h)]
 return[r['id'] for r in json.loads((root/'analysis/aka-release-header-report.json').read_text(encoding='utf-8'))['releases']]

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--random-wrapper-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();data=a.rom.read_bytes();digest=hashlib.sha256(data).hexdigest();identity={'release':a.release,'sha256':digest}
 if digest!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 wrapper=json.loads(a.random_wrapper_report.read_text(encoding='utf-8'))
 if wrapper['target']!=identity:p.error('Random wrapper identity mismatch')
 found=locate(data,wrapper['function']['address'])
 if len(found)!=1:p.error(f'expected exactly one BattleRandom, found {len(found)}')
 report={'schema_version':1,'target':identity,'function':{'name':'BattleRandom',**found[0]},'semantics':{'non_link':'tail-jump to Random','link':'consume shared ten-byte list and refresh nine seeds at boundary','synchronization':'shared state keeps linked peers aligned','return_register':'A'},'naming_basis':{'repository':'pret/pokered','commit':a.reference_commit,'path':'engine/battle/core.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  releases=ids(a.root);outputs=[Path('src/battle_random.asm'),*(Path(f'analysis/{r}-battle-random.json')for r in releases),Path('research/battle-random-reconstruction.md'),Path('tests/test_battle_random_reconstruction.py')];missing=[x.as_posix()for x in outputs if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'BattleRandom','releases':releases,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/locate_gen1_battle_random.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in outputs],'raw_rom_bytes_included':False};(a.root/'manifests/battle-random-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
