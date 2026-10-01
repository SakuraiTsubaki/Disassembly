#!/usr/bin/env python3
"""Compose a Game Boy 1bpp tile range using an indexed ROM tilemap."""
from __future__ import annotations
import argparse,hashlib,json,struct,zlib
from pathlib import Path

def _chunk(k,p): return struct.pack('>I',len(p))+k+p+struct.pack('>I',zlib.crc32(k+p))
def render(tiles:bytes,tilemap:bytes,base_id:int,blank_ids:set[int],scale:int=4):
 if len(tiles)%8: raise ValueError('tile data length must be divisible by 8')
 logical=[[255]*(len(tilemap)*8) for _ in range(8)]; count=len(tiles)//8
 for cell,tile_id in enumerate(tilemap):
  if tile_id in blank_ids: continue
  index=tile_id-base_id
  if not 0<=index<count: raise ValueError(f'tile id {tile_id:#04x} is outside the tile set')
  for y,bits in enumerate(tiles[index*8:index*8+8]):
   for x in range(8): logical[y][cell*8+x]=0 if bits&(0x80>>x) else 255
 rows=[]
 for row in logical:
  line=b'\0'+bytes(v for v in row for _ in range(scale)); rows.extend([line]*scale)
 ihdr=struct.pack('>IIBBBBB',len(tilemap)*8*scale,8*scale,8,0,0,0,0)
 return b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',ihdr)+_chunk(b'IDAT',zlib.compress(b''.join(rows),9))+_chunk(b'IEND',b'')
def compose(rom:bytes,tiles_offset:int,tile_count:int,tilemap_offset:int,tilemap_length:int,base_id:int,blank_ids:set[int],expected_sha256:str|None=None):
 digest=hashlib.sha256(rom).hexdigest()
 if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError(f'ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}')
 tiles=rom[tiles_offset:tiles_offset+tile_count*8]; tilemap=rom[tilemap_offset:tilemap_offset+tilemap_length]
 if len(tiles)!=tile_count*8 or len(tilemap)!=tilemap_length: raise ValueError('requested range extends past the ROM')
 png=render(tiles,tilemap,base_id,blank_ids)
 return png,{'rom_size':len(rom),'rom_sha256':digest,'tiles_offset':tiles_offset,'tiles_length':len(tiles),'tiles_sha256':hashlib.sha256(tiles).hexdigest(),'tile_count':tile_count,'base_tile_id':f'0x{base_id:02x}','tilemap_offset':tilemap_offset,'tilemap_length':len(tilemap),'tilemap_sha256':hashlib.sha256(tilemap).hexdigest(),'blank_tile_ids':[f'0x{x:02x}' for x in sorted(blank_ids)],'format':'game-boy-1bpp-indexed-tilemap','png_sha256':hashlib.sha256(png).hexdigest()}
def main():
 p=argparse.ArgumentParser();p.add_argument('rom',type=Path);p.add_argument('--tiles-offset',required=True,type=lambda v:int(v,0));p.add_argument('--tile-count',required=True,type=int);p.add_argument('--tilemap-offset',required=True,type=lambda v:int(v,0));p.add_argument('--tilemap-length',required=True,type=int);p.add_argument('--base-id',required=True,type=lambda v:int(v,0));p.add_argument('--blank-id',action='append',default=[],type=lambda v:int(v,0));p.add_argument('--expected-sha256');p.add_argument('--png',required=True,type=Path);p.add_argument('--report',required=True,type=Path);a=p.parse_args();png,r=compose(a.rom.read_bytes(),a.tiles_offset,a.tile_count,a.tilemap_offset,a.tilemap_length,a.base_id,set(a.blank_id),a.expected_sha256);a.png.parent.mkdir(parents=True,exist_ok=True);a.report.parent.mkdir(parents=True,exist_ok=True);a.png.write_bytes(png);a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
