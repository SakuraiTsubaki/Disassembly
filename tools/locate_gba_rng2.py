#!/usr/bin/env python3
"""Locate and verify Emerald's independent SeedRng2/Random2 Thumb pair."""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from pathlib import Path
ROM_BASE=0x08000000;MULTIPLIER=1103515245;INCREMENT=24691
SEED=(0x0400,0x0C00,0x4901,0x6008,0x4770);RANDOM=(0x4A04,0x6811,0x4804,0x4348,0x4904,0x1840,0x6010,0x0C00,0x4770)
def hits(data,pattern):
 n=struct.pack(f'<{len(pattern)}H',*pattern);out=[];s=0
 while True:
  o=data.find(n,s)
  if o<0:break
  if o%2==0:out.append(o)
  s=o+1
 return out
def rec(data,o,n):return {'address':f'0x{ROM_BASE+o:08X}','rom_offset':o,'range_end_exclusive':f'0x{ROM_BASE+o+n:08X}','length':n,'code_sha256':hashlib.sha256(data[o:o+n]).hexdigest()}
def locate(data):
 rb=struct.pack(f'<{len(RANDOM)}H',*RANDOM);pairs=[]
 for s in hits(data,SEED):
  r=s+16
  if data[r:r+len(rb)]==rb:
   state=struct.unpack_from('<I',data,s+12)[0]
   if state==struct.unpack_from('<I',data,r+20)[0]:pairs.append((s,r,state))
 if len(pairs)!=1:raise ValueError(f'expected one adjacent SeedRng2/Random2 pair, found {len(pairs)}')
 s,r,state=pairs[0]
 if struct.unpack_from('<I',data,r+24)[0]!=MULTIPLIER or struct.unpack_from('<I',data,r+28)[0]!=INCREMENT:raise ValueError('LCG constants mismatch')
 return {'globals':{'gRng2Value':f'0x{state:08X}'},'functions':{'SeedRng2':rec(data,s,len(SEED)*2),'Random2':rec(data,r,len(RANDOM)*2)},'algorithm':{'state_bits':32,'multiplier':MULTIPLIER,'increment':INCREMENT,'return_bits':'state[31:16]','independent_from_primary':True}}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest()
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 try:r=locate(d)
 except(ValueError,struct.error)as e:p.error(str(e))
 r={'schema_version':1,'target':{'release':a.release,'sha256':h},**r,'naming_basis':{'repository':'pret/pokeemerald','commit':a.reference_commit,'path':'src/random.c','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  with(a.root/'research/releases.csv').open(encoding='utf-8',newline='')as f:ids=[x['id']for x in csv.DictReader(f)]
  out=[Path('src/random2.asm'),*(Path(f'analysis/{x}-rng2.json')for x in ids),Path('research/rng2-reconstruction.md'),Path('tests/test_rng2_reconstruction.py')];missing=[x.as_posix()for x in out if not(a.root/x).is_file()]
  if missing:p.error('missing manifest output(s): '+', '.join(missing))
  m={'schema_version':1,'functions':['SeedRng2','Random2'],'releases':ids,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/locate_gba_rng2.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()}for x in out],'raw_rom_bytes_included':False};(a.root/'manifests/rng2-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0
if __name__=='__main__':raise SystemExit(main())
