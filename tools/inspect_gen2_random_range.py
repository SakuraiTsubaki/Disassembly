#!/usr/bin/env python3
"""Verify the Generation II rejection-sampling RandomRange routine."""
from __future__ import annotations

import argparse, csv, hashlib, json
from pathlib import Path

LENGTH=26

def inspect(data:bytes, offset:int, random_address:int, h_random_add:int):
    if offset<0 or offset+LENGTH>len(data): return None
    c=data[offset:offset+LENGTH]
    fixed={0:0xC5,1:0x4F,2:0xAF,3:0x91,4:0x91,5:0x30,6:0xFD,7:0x81,8:0x47,9:0xC5,10:0xCD,13:0xF0,15:0x4F,16:0x80,17:0x38,18:0xF7,19:0x79,20:0xC1,21:0xCD,24:0xC1,25:0xC9}
    if any(c[i]!=v for i,v in fixed.items()): return None
    if int.from_bytes(c[11:13],'little')!=random_address or 0xFF00+c[14]!=h_random_add: return None
    divide=int.from_bytes(c[22:24],'little')
    if not 0<=random_address<0x4000 or not 0<=divide<0x4000: return None
    bank=offset//0x4000; address=offset if bank==0 else 0x4000+offset%0x4000
    if address+7+int.from_bytes(c[6:7],'little',signed=True)!=address+4: return None
    if address+19+int.from_bytes(c[18:19],'little',signed=True)!=address+10: return None
    return {'rom_offset':offset,'bank':bank,'address':address,'range_end_exclusive':offset+LENGTH,'length':LENGTH,'code_sha256':hashlib.sha256(c).hexdigest(),'dependencies':{'Random':{'bank':0,'address':random_address},'hRandomAdd':h_random_add,'SimpleDivide':{'bank':0,'address':divide}},'control_flow':{'modulo_loop':{'from_offset':5,'to_offset':4},'rejection_loop':{'from_offset':17,'to_offset':10}},'input':'A (exclusive upper bound)','output':'A (uniform value below input for nonzero input)'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--wrapper-report',type=Path,required=True);p.add_argument('--random-report',type=Path,required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args()
    data=a.rom.read_bytes();digest=hashlib.sha256(data).hexdigest();identity={'release':a.release,'sha256':digest}
    if digest!=a.expected_sha256.lower(): p.error('ROM SHA-256 mismatch')
    wrapper=json.loads(a.wrapper_report.read_text(encoding='utf-8'));random=json.loads(a.random_report.read_text(encoding='utf-8'))
    if wrapper['target']!=identity or random['target']!=identity: p.error('dependency report identity mismatch')
    f=inspect(data,wrapper['function']['range_end_exclusive'],random['function']['address'],random['function']['globals']['hRandomAdd'])
    if f is None: p.error('RandomRange does not match the verified structure')
    report={'schema_version':1,'target':identity,'function':{'name':'RandomRange',**f},'semantics':{'method':'rejection sampling followed by SimpleDivide','bias_control':'reject values in the incomplete high tail','valid_input':'1..255','return_register':'A'},'naming_basis':{'repository':a.reference_repository,'commit':a.reference_commit,'path':'home/random.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    if a.root:
      with (a.root/'research/releases.csv').open(encoding='utf-8',newline='') as h: releases=[r['id'] for r in csv.DictReader(h)]
      outputs=[Path('src/random_range.asm'),*(Path(f'analysis/{r}-random-range.json') for r in releases),Path('research/random-range-reconstruction.md'),Path('tests/test_random_range_reconstruction.py')]
      missing=[x.as_posix() for x in outputs if not(a.root/x).is_file()]
      if missing:p.error('missing manifest output(s): '+', '.join(missing))
      manifest={'schema_version':1,'function':'RandomRange','releases':releases,'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/inspect_gen2_random_range.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':x.as_posix(),'sha256':hashlib.sha256((a.root/x).read_bytes()).hexdigest()} for x in outputs],'raw_rom_bytes_included':False}
      (a.root/'manifests/random-range-reconstruction.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0
if __name__=='__main__':raise SystemExit(main())
