#!/usr/bin/env python3
"""Extract a GBA BIOS-LZ77 stream and render its 4bpp tiles as a PNG."""
from __future__ import annotations
import argparse,hashlib,json,math,struct,zlib
from pathlib import Path

def decompress(data:bytes,offset:int=0):
 if offset+4>len(data) or data[offset]!=0x10: raise ValueError('missing GBA LZ77 header')
 size=int.from_bytes(data[offset+1:offset+4],'little');out=bytearray();i=offset+4
 while len(out)<size:
  if i>=len(data): raise ValueError('truncated flag byte')
  flags=data[i];i+=1
  for bit in range(7,-1,-1):
   if len(out)>=size: break
   if flags&(1<<bit):
    if i+2>len(data): raise ValueError('truncated compressed token')
    a,b=data[i],data[i+1];i+=2;length=(a>>4)+3;distance=(((a&15)<<8)|b)+1
    if distance>len(out): raise ValueError('invalid LZ77 lookback')
    for _ in range(length):
     if len(out)>=size: break
     out.append(out[-distance])
   else:
    if i>=len(data): raise ValueError('truncated literal')
    out.append(data[i]);i+=1
 return bytes(out),i-offset

def _chunk(kind,payload): return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))
def parse_jasc_palette(data:bytes):
 lines=data.decode('ascii').splitlines()
 if len(lines)<4 or lines[0]!='JASC-PAL' or lines[1]!='0100': raise ValueError('invalid JASC palette')
 count=int(lines[2]);colors=[tuple(map(int,line.split())) for line in lines[3:3+count]]
 if len(colors)!=count or any(len(c)!=3 or any(v<0 or v>255 for v in c) for c in colors): raise ValueError('invalid JASC palette colors')
 return colors

def render(raw:bytes,tiles_per_row:int,scale:int=2,palette=None):
 if not raw or len(raw)%32: raise ValueError('4bpp tile data length must be divisible by 32')
 count=len(raw)//32;rows=math.ceil(count/tiles_per_row);w=tiles_per_row*8;h=rows*8
 pixels=[[0]*w for _ in range(h)]
 for tile in range(count):
  tx,ty=tile%tiles_per_row,tile//tiles_per_row
  for n,value in enumerate(raw[tile*32:tile*32+32]):
   y=n//4;x=(n%4)*2;pixels[ty*8+y][tx*8+x]=value&15;pixels[ty*8+y][tx*8+x+1]=value>>4
 scan=[]
 for row in pixels:
  if palette:
   if len(palette)<16: raise ValueError('4bpp rendering requires at least 16 palette colors')
   line=b'\0'+bytes(channel for v in row for _ in range(scale) for channel in palette[v])
  else: line=b'\0'+bytes((15-v)*17 for v in row for _ in range(scale))
  scan.extend([line]*scale)
 ihdr=struct.pack('>IIBBBBB',w*scale,h*scale,8,2 if palette else 0,0,0,0)
 return b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',ihdr)+_chunk(b'IDAT',zlib.compress(b''.join(scan),9))+_chunk(b'IEND',b'')

def extract(rom:bytes,offset:int,tiles_per_row:int,expected_sha256:str|None=None,palette_bytes:bytes|None=None):
 digest=hashlib.sha256(rom).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError(f'ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}')
 raw,used=decompress(rom,offset);palette=parse_jasc_palette(palette_bytes) if palette_bytes else None;png=render(raw,tiles_per_row,palette=palette)
 report={'rom_size':len(rom),'rom_sha256':digest,'source_offset':offset,'compressed_length':used,'compressed_sha256':hashlib.sha256(rom[offset:offset+used]).hexdigest(),'decompressed_length':len(raw),'decompressed_sha256':hashlib.sha256(raw).hexdigest(),'tile_count':len(raw)//32,'tiles_per_row':tiles_per_row,'format':'gba-bios-lz77-to-4bpp-tiles','palette':'jasc-pal' if palette else 'grayscale-index-preview','png_sha256':hashlib.sha256(png).hexdigest(),'raw_rom_bytes_included':False}
 if palette_bytes: report['palette_sha256']=hashlib.sha256(palette_bytes).hexdigest()
 return png,report

def main():
 p=argparse.ArgumentParser();p.add_argument('rom',type=Path);p.add_argument('--offset',required=True,type=lambda x:int(x,0));p.add_argument('--tiles-per-row',required=True,type=int);p.add_argument('--expected-sha256');p.add_argument('--palette',type=Path);p.add_argument('--png',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args()
 png,report=extract(a.rom.read_bytes(),a.offset,a.tiles_per_row,a.expected_sha256,a.palette.read_bytes() if a.palette else None);a.png.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);a.png.write_bytes(png);a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
