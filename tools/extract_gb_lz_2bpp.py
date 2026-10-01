#!/usr/bin/env python3
"""Decompress the Pokémon Gen II LZ format and render 2bpp tiles."""
from __future__ import annotations
import argparse,hashlib,json,math,struct,zlib
from pathlib import Path
PAL=(255,170,85,0)
def flip(v): return int(f'{v:08b}'[::-1],2)
def decompress(data:bytes,offset:int=0):
 out=bytearray();i=offset
 while True:
  if i>=len(data): raise ValueError('unterminated LZ stream')
  h=data[i];i+=1
  if h==0xff: return bytes(out),i-offset
  cmd=h>>5;length=(h&31)+1
  if cmd==7:
   if i>=len(data): raise ValueError('incomplete long command')
   cmd=(h&31)>>2;length=(((h&3)<<8)|data[i])+1;i+=1
  if cmd==0:
   if i+length>len(data): raise ValueError('incomplete literal')
   out.extend(data[i:i+length]);i+=length
  elif cmd==1:
   if i>=len(data): raise ValueError('incomplete iterate')
   out.extend([data[i]]*length);i+=1
  elif cmd==2:
   if i+2>len(data): raise ValueError('incomplete alternate')
   a,b=data[i:i+2];i+=2;out.extend(a if n%2==0 else b for n in range(length))
  elif cmd==3: out.extend(bytes(length))
  elif cmd in (4,5,6):
   if i>=len(data): raise ValueError('incomplete lookback')
   first=data[i];i+=1
   if first&0x80: base=len(out)-((first&0x7f)+1)
   else:
    if i>=len(data): raise ValueError('incomplete absolute lookback')
    base=(first<<8)|data[i];i+=1
   if base<0 or base>=len(out): raise ValueError('invalid lookback')
   for n in range(length):
    at=base-n if cmd==6 else base+n
    if at<0 or at>=len(out): raise ValueError('lookback outside output')
    v=out[at];out.append(flip(v) if cmd==5 else v)
  else: raise ValueError(f'invalid command {cmd}')
def _chunk(k,p): return struct.pack('>I',len(p))+k+p+struct.pack('>I',zlib.crc32(k+p))
def render(raw:bytes,tiles_per_row:int,scale:int=2):
 if not raw or len(raw)%16: raise ValueError('decompressed size must be 2bpp tiles')
 count=len(raw)//16;rows=math.ceil(count/tiles_per_row);logical=[[255]*(tiles_per_row*8) for _ in range(rows*8)]
 for t in range(count):
  tx,ty=t%tiles_per_row,t//tiles_per_row
  for y in range(8):
   lo,hi=raw[t*16+y*2:t*16+y*2+2]
   for x in range(8): logical[ty*8+y][tx*8+x]=PAL[((lo>>(7-x))&1)|(((hi>>(7-x))&1)<<1)]
 scan=[]
 for row in logical:
  line=b'\0'+bytes(v for v in row for _ in range(scale));scan.extend([line]*scale)
 ihdr=struct.pack('>IIBBBBB',tiles_per_row*8*scale,rows*8*scale,8,0,0,0,0)
 return b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',ihdr)+_chunk(b'IDAT',zlib.compress(b''.join(scan),9))+_chunk(b'IEND',b'')
def extract(rom:bytes,offset:int,tiles_per_row:int,expected_sha256:str|None=None):
 digest=hashlib.sha256(rom).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError(f'ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}')
 raw,used=decompress(rom,offset);png=render(raw,tiles_per_row)
 return png,{'rom_size':len(rom),'rom_sha256':digest,'source_offset':offset,'compressed_length':used,'compressed_sha256':hashlib.sha256(rom[offset:offset+used]).hexdigest(),'decompressed_length':len(raw),'decompressed_sha256':hashlib.sha256(raw).hexdigest(),'tile_count':len(raw)//16,'tiles_per_row':tiles_per_row,'format':'pokemon-gen2-lz-to-game-boy-2bpp','png_sha256':hashlib.sha256(png).hexdigest()}
def main():
 p=argparse.ArgumentParser();p.add_argument('rom',type=Path);p.add_argument('--offset',required=True,type=lambda v:int(v,0));p.add_argument('--tiles-per-row',required=True,type=int);p.add_argument('--expected-sha256');p.add_argument('--png',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args();png,r=extract(a.rom.read_bytes(),a.offset,a.tiles_per_row,a.expected_sha256);a.png.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);a.png.write_bytes(png);a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()

