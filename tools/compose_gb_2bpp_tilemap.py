#!/usr/bin/env python3
"""Compose an indexed Game Boy 2bpp tilemap from verified ROM ranges."""

from __future__ import annotations
import argparse, hashlib, json, struct, zlib
from pathlib import Path

PALETTE=(255,170,85,0)

def _chunk(kind,payload): return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))

def decode_tile(raw: bytes):
    pixels=[]
    for y in range(8):
        low,high=raw[y*2:y*2+2]; row=[]
        for x in range(8):
            value=((low>>(7-x))&1)|(((high>>(7-x))&1)<<1); row.append(PALETTE[value])
        pixels.append(row)
    return pixels

def render(tiles: bytes, tilemap: bytes, width: int, height: int, blank_ids: set[int], remap: dict[int,int]|None=None, scale: int=2):
    if len(tiles)%16: raise ValueError('tile data length must be divisible by 16')
    if len(tilemap)!=width*height: raise ValueError('tilemap length does not match dimensions')
    decoded=[decode_tile(tiles[i:i+16]) for i in range(0,len(tiles),16)]; logical=[[255]*(width*8) for _ in range(height*8)]; remap=remap or {}
    for cell,tile_id in enumerate(tilemap):
        if tile_id in blank_ids: continue
        source_id=remap.get(tile_id,tile_id)
        if source_id>=len(decoded): raise ValueError(f'tile id {tile_id:#04x} is outside the tile set')
        cx,cy=cell%width,cell//width
        for y,row in enumerate(decoded[source_id]): logical[cy*8+y][cx*8:cx*8+8]=row
    rows=[]
    for row in logical:
        line=b'\0'+bytes(v for v in row for _ in range(scale)); rows.extend([line]*scale)
    ihdr=struct.pack('>IIBBBBB',width*8*scale,height*8*scale,8,0,0,0,0)
    return b'\x89PNG\r\n\x1a\n'+_chunk(b'IHDR',ihdr)+_chunk(b'IDAT',zlib.compress(b''.join(rows),9))+_chunk(b'IEND',b'')

def compose(rom: bytes, tiles_offset: int, tile_count: int, tilemap_offset: int, width: int, height: int, blank_ids: set[int], expected_sha256: str|None=None, extra_offset: int|None=None, extra_count: int=0, extra_first_id: int|None=None):
    digest=hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError(f'ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}')
    tiles=rom[tiles_offset:tiles_offset+tile_count*16]; tilemap=rom[tilemap_offset:tilemap_offset+width*height]
    if len(tiles)!=tile_count*16 or len(tilemap)!=width*height: raise ValueError('requested range extends past the ROM')
    remap={}; extra=b''
    if extra_count:
        if extra_offset is None or extra_first_id is None: raise ValueError('extra tile offset and first id are required')
        extra=rom[extra_offset:extra_offset+extra_count*16]
        if len(extra)!=extra_count*16: raise ValueError('extra tile range extends past the ROM')
        remap={extra_first_id+i:tile_count+i for i in range(extra_count)}
    combined=tiles+extra; png=render(combined,tilemap,width,height,blank_ids,remap)
    report={'rom_size':len(rom),'rom_sha256':digest,'tiles_offset':tiles_offset,'tiles_length':len(tiles),'tiles_sha256':hashlib.sha256(tiles).hexdigest(),'tile_count':tile_count,'tilemap_offset':tilemap_offset,'tilemap_length':len(tilemap),'tilemap_sha256':hashlib.sha256(tilemap).hexdigest(),'tilemap_width':width,'tilemap_height':height,'blank_tile_ids':[f'0x{x:02x}' for x in sorted(blank_ids)],'format':'game-boy-2bpp-indexed-tilemap','png_sha256':hashlib.sha256(png).hexdigest()}
    if extra: report['extra_tiles']={'offset':extra_offset,'length':len(extra),'sha256':hashlib.sha256(extra).hexdigest(),'count':extra_count,'first_tile_id':f'0x{extra_first_id:02x}'}
    return png,report

def main():
    p=argparse.ArgumentParser(); p.add_argument('rom',type=Path); p.add_argument('--tiles-offset',required=True,type=lambda v:int(v,0)); p.add_argument('--tile-count',required=True,type=int); p.add_argument('--tilemap-offset',required=True,type=lambda v:int(v,0)); p.add_argument('--width',required=True,type=int); p.add_argument('--height',required=True,type=int); p.add_argument('--blank-id',action='append',default=[],type=lambda v:int(v,0)); p.add_argument('--extra-tiles-offset',type=lambda v:int(v,0)); p.add_argument('--extra-tile-count',type=int,default=0); p.add_argument('--extra-first-id',type=lambda v:int(v,0)); p.add_argument('--expected-sha256'); p.add_argument('--png',required=True,type=Path); p.add_argument('--report',required=True,type=Path); a=p.parse_args()
    png,r=compose(a.rom.read_bytes(),a.tiles_offset,a.tile_count,a.tilemap_offset,a.width,a.height,set(a.blank_id),a.expected_sha256,a.extra_tiles_offset,a.extra_tile_count,a.extra_first_id); a.png.parent.mkdir(parents=True,exist_ok=True); a.report.parent.mkdir(parents=True,exist_ok=True); a.png.write_bytes(png); a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__': main()
