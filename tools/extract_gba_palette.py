#!/usr/bin/env python3
"""Extract a GBA BGR555 palette as reproducible JASC-PAL text."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def decode(data:bytes,offset:int,count:int):
 if count<1 or offset<0 or offset+count*2>len(data): raise ValueError('palette range is outside ROM')
 colors=[]
 for i in range(count):
  value=int.from_bytes(data[offset+i*2:offset+i*2+2],'little')
  colors.append(tuple(((value>>shift)&31)*255//31 for shift in (0,5,10)))
 return colors

def jasc(colors):
 return ('JASC-PAL\n0100\n'+str(len(colors))+'\n'+''.join(f'{r} {g} {b}\n' for r,g,b in colors)).encode('ascii')

def extract(rom:bytes,offset:int,count:int,expected_sha256:str|None=None):
 digest=hashlib.sha256(rom).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError(f'ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}')
 source=rom[offset:offset+count*2];output=jasc(decode(rom,offset,count))
 return output,{'rom_size':len(rom),'rom_sha256':digest,'source_offset':offset,'color_count':count,'source_format':'gba-bgr555','source_length':len(source),'source_sha256':hashlib.sha256(source).hexdigest(),'output_format':'JASC-PAL','palette_sha256':hashlib.sha256(output).hexdigest(),'raw_rom_bytes_included':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('rom',type=Path);p.add_argument('--offset',required=True,type=lambda x:int(x,0));p.add_argument('--colors',required=True,type=int);p.add_argument('--expected-sha256');p.add_argument('--palette',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
 palette,report=extract(a.rom.read_bytes(),a.offset,a.colors,a.expected_sha256);a.palette.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);a.palette.write_bytes(palette);a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
