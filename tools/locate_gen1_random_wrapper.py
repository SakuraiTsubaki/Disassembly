#!/usr/bin/env python3
"""Locate and verify the Generation I home-bank Random wrapper."""
from __future__ import annotations

import argparse,csv,hashlib,json
from pathlib import Path

LENGTH=17

def locate(data:bytes,target_bank:int,target_address:int,h_random_add:int):
    prefix=bytes((0xE5,0xD5,0xC5,0x06,target_bank,0x21,target_address&0xff,target_address>>8,0xCD))
    suffix=bytes((0xF0,h_random_add&0xff,0xC1,0xD1,0xE1,0xC9))
    out=[];start=0
    while True:
      o=data.find(prefix,start)
      if o<0:break
      c=data[o:o+LENGTH]
      if len(c)==LENGTH and c[11:]==suffix:
       bank=o//0x4000;address=o if bank==0 else 0x4000+o%0x4000;bankswitch=int.from_bytes(c[9:11],'little')
       if bank==0 and bankswitch<0x4000:
        out.append({'rom_offset':o,'bank':bank,'address':address,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(c).hexdigest(),'dependencies':{'Random_':{'bank':target_bank,'address':target_address},'hRandomAdd':h_random_add,'Bankswitch':{'bank':0,'address':bankswitch}},'preserved_registers':['BC','DE','HL'],'return_register':'A'})
      start=o+1
    return out

def release_ids(root:Path):
    p=root/'research/releases.csv'
    if p.is_file():
      with p.open(encoding='utf-8',newline='') as h:return [r['id'] for r in csv.DictReader(h)]
    report=json.loads((root/'analysis/aka-release-header-report.json').read_text(encoding='utf-8'));return [r['id'] for r in report['releases']]

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--random-core-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args()
    data=a.rom.read_bytes();digest=hashlib.sha256(data).hexdigest();identity={'release':a.release,'sha256':digest}
    if digest!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
    core=json.loads(a.random_core_report.read_text(encoding='utf-8'))
    if core['target']!=identity:p.error('Random_ report identity mismatch')
    f=core['function'];matches=locate(data,f['bank'],f['address'],f['globals']['hRandomAdd'])
    if len(matches)!=1:p.error(f'expected exactly one Random wrapper, found {len(matches)}')
    report={'schema_version':1,'target':identity,'function':{'name':'Random',**matches[0]},'semantics':{'operation':'farcall Random_ and return hRandomAdd','register_preservation':'BC, DE, and HL are restored','return_register':'A'},'naming_basis':{'repository':'pret/pokered','commit':a.reference_commit,'path':'home/random.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    if a.root:
      releases=release_ids(a.root);outputs=[Path('src/random_wrapper.asm'),*(Path(f'analysis/{r}-random-wrapper.json') for r in releases),Path('research/random-wrapper-reconstruction.md'),Path('tests/test_random_wrapper_reconstruction.py')]
      missing=[x.as_posix() for x in outputs if not(a.root/x).is_file()]
      if missing:p.error('missing manifest output(s): '+', '.join(missing))
      manifest={'schema_version':1,'function':'Random','releases':releases,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/locate_gen1_random_wrapper.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()} for x in outputs],'raw_rom_bytes_included':False}
      (a.root/'manifests/random-wrapper-reconstruction.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
