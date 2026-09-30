#!/usr/bin/env python3
"""Extract an uncompressed Game Boy 2bpp tile range as a deterministic PNG."""

from __future__ import annotations
import argparse, hashlib, json, math, struct, zlib
from pathlib import Path

TILE_BYTES=16; TILE_SIZE=8; PALETTE=(255,170,85,0)

def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack('>I',len(payload))+kind+payload+struct.pack('>I',zlib.crc32(kind+payload))

def render(raw: bytes, tiles_per_row: int, scale: int=2) -> bytes:
    if not raw or len(raw)%TILE_BYTES: raise ValueError('2bpp input length must be a non-zero multiple of 16 bytes')
    if tiles_per_row<=0: raise ValueError('tiles_per_row must be positive')
    count=len(raw)//TILE_BYTES; rows=math.ceil(count/tiles_per_row); width=tiles_per_row*TILE_SIZE; height=rows*TILE_SIZE
    logical=[[255]*width for _ in range(height)]
    for tile in range(count):
        tx,ty=tile%tiles_per_row,tile//tiles_per_row
        for y in range(8):
            low,high=raw[tile*16+y*2:tile*16+y*2+2]
            for x in range(8):
                value=((low>>(7-x))&1)|(((high>>(7-x))&1)<<1)
                logical[ty*8+y][tx*8+x]=PALETTE[value]
    scanlines=[]
    for row in logical:
        line=b'\0'+bytes(v for v in row for _ in range(scale)); scanlines.extend([line]*scale)
    signature=b'\x89PNG\r\n\x1a\n'; ihdr=struct.pack('>IIBBBBB',width*scale,height*scale,8,0,0,0,0)
    return signature+_chunk(b'IHDR',ihdr)+_chunk(b'IDAT',zlib.compress(b''.join(scanlines),9))+_chunk(b'IEND',b'')

def extract(rom: bytes, offset: int, tile_count: int, tiles_per_row: int, expected_sha256: str|None=None):
    digest=hashlib.sha256(rom).hexdigest()
    if expected_sha256 and digest.lower()!=expected_sha256.lower(): raise ValueError(f'ROM SHA-256 mismatch: expected {expected_sha256}, got {digest}')
    length=tile_count*TILE_BYTES; raw=rom[offset:offset+length]
    if len(raw)!=length: raise ValueError('requested tile range extends past the ROM')
    png=render(raw,tiles_per_row)
    return png,{'rom_size':len(rom),'rom_sha256':digest,'source_offset':offset,'source_length':length,'source_sha256':hashlib.sha256(raw).hexdigest(),'format':'game-boy-2bpp-8x8-tiles','tile_count':tile_count,'tiles_per_row':tiles_per_row,'logical_width':tiles_per_row*8,'logical_height':math.ceil(tile_count/tiles_per_row)*8,'png_sha256':hashlib.sha256(png).hexdigest()}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument('rom',type=Path); p.add_argument('--offset',required=True,type=lambda v:int(v,0)); p.add_argument('--tile-count',required=True,type=int); p.add_argument('--tiles-per-row',required=True,type=int); p.add_argument('--expected-sha256'); p.add_argument('--png',required=True,type=Path); p.add_argument('--report',required=True,type=Path); a=p.parse_args()
    png,report=extract(a.rom.read_bytes(),a.offset,a.tile_count,a.tiles_per_row,a.expected_sha256); a.png.parent.mkdir(parents=True,exist_ok=True); a.report.parent.mkdir(parents=True,exist_ok=True); a.png.write_bytes(png); a.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8'); return 0

if __name__=='__main__': raise SystemExit(main())
