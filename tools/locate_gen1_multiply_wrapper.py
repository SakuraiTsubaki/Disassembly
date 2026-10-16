#!/usr/bin/env python3
"""Locate and verify the Generation I home-bank Multiply wrapper."""
from __future__ import annotations
import argparse,csv,hashlib,json
from pathlib import Path
LENGTH=13
def core_offset(bank,address):return bank*0x4000+address-0x4000
def looks_like_core(data,o):
 return o>=0 and o+21<=len(data) and data[o:o+5]==bytes((0x3E,8,0x47,0xAF,0xE0)) and data[o+6]==0xE0 and data[o+8]==0xE0 and data[o+10]==0xE0 and data[o+12]==0xE0 and data[o+14]==0xF0 and data[o+16:o+18]==bytes((0xCB,0x3F)) and data[o+18]==0xE0 and data[o+20]==0x30
def locate(data):
 out=[]
 for o in range(0,min(0x4000,len(data))-LENGTH+1):
  c=data[o:o+LENGTH]
  if c[0:3]!=bytes((0xE5,0xC5,0x21))or c[5]!=0x06 or c[7]!=0xCD or c[10:13]!=bytes((0xC1,0xE1,0xC9)):continue
  address=int.from_bytes(c[3:5],'little');bank=c[6];switch=int.from_bytes(c[8:10],'little')
  if bank==0 or not 0x4000<=address<0x8000 or switch>=0x4000:continue
  target=core_offset(bank,address)
  if not looks_like_core(data,target):continue
  out.append({'rom_offset':o,'bank':0,'address':o,'range_end_exclusive':o+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(c).hexdigest(),'far_call':{'target':{'bank':bank,'address':address,'rom_offset':target},'bankswitch':{'bank':0,'address':switch}},'preserved_registers':['BC','HL']})
 return out
def release_ids(root):
 p=root/'research/releases.csv'
 if p.is_file():
  with p.open(encoding='utf-8',newline='')as f:return [x['id']for x in csv.DictReader(f)]
 return [x['id']for x in json.loads((root/'analysis/aka-release-header-report.json').read_text(encoding='utf-8'))['releases']]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest();identity={'release':a.release,'sha256':h}
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 matches=locate(d)
 if len(matches)!=1:p.error(f'expected exactly one Multiply wrapper, found {len(matches)}')
 r={'schema_version':1,'target':identity,'function':{'name':'Multiply',**matches[0]},'semantics':{'operation':'preserve HL/BC and far-call _Multiply','input':'three-byte hMultiplicand and hMultiplier','output':'four-byte hProduct','register_preservation':'BC and HL are restored'},'naming_basis':{'repository':'pret/pokered','commit':a.reference_commit,'path':'home/math.asm','macro_path':'macros/farcall.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  ids=release_ids(a.root);out=[Path('src/multiply_wrapper.asm'),*(Path(f'analysis/{x}-multiply-wrapper.json')for x in ids),Path('research/multiply-wrapper-reconstruction.md'),Path('tests/test_multiply_wrapper_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'function':'Multiply','releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/locate_gen1_multiply_wrapper.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/multiply-wrapper-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
