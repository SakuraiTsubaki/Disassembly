#!/usr/bin/env python3
"""Extract the complete Generation II Pokémon footprint atlas."""
from __future__ import annotations
import argparse,csv,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import extract_gb_1bpp

SLOTS=256;TILES_PER_SLOT=4;LENGTH=SLOTS*TILES_PER_SLOT*8
def digest(data):return hashlib.sha256(data).hexdigest()
def file_hash(path):return digest(path.read_bytes())
def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def unique_offset(data,signature):
 found=[];start=0
 while True:
  offset=data.find(signature,start)
  if offset<0:break
  found.append(offset);start=offset+1
 if len(found)!=1:raise ValueError(f'expected one footprint atlas, found {len(found)}')
 return found[0]
def rom_index(directory):
 result={}
 for path in directory.iterdir():
  if path.is_file() and path.suffix.lower() in ('.gb','.gbc'):result.setdefault(file_hash(path),path)
 return result
def build(root,rom_dir,origin_release,origin_offset,game,reference_repository,reference_commit):
 with (root/'research/releases.csv').open(encoding='utf-8',newline='')as h:rows=list(csv.DictReader(h))
 by_id={r['id']:r for r in rows};origin=by_id[origin_release];roms=rom_index(rom_dir);origin_sha=origin['sha256']
 if origin_sha not in roms:raise ValueError('origin ROM is missing')
 data=roms[origin_sha].read_bytes();raw=data[origin_offset:origin_offset+LENGTH]
 if len(raw)!=LENGTH:raise ValueError('origin range leaves ROM')
 raw_hash=digest(raw);png=extract_gb_1bpp.render(raw,16,scale=2);png_path=Path('graphics/pokemon/footprints-atlas.png');(root/png_path).parent.mkdir(parents=True,exist_ok=True);(root/png_path).write_bytes(png)
 layout_path=Path('graphics/pokemon/footprints-atlas.json');slots=[{'slot':i+1,'kind':'pokemon' if i<251 else 'unused','logical_rect':{'x':(i%8)*16,'y':(i//8)*16,'width':16,'height':16},'png_rect':{'x':(i%8)*32,'y':(i//8)*32,'width':32,'height':32}}for i in range(SLOTS)];write_json(root/layout_path,{'schema_version':1,'layout':'8 footprints per row; top tile row followed by bottom tile row','slot_count':SLOTS,'official_species_slots':251,'unused_slots':5,'logical_width':128,'logical_height':512,'png_scale':2,'slots':slots});outputs=[png_path,layout_path];records=[]
 for row in rows:
  sha=row['sha256'];rid=row['id']
  if sha not in roms:raise ValueError(f'missing release ROM: {rid}')
  target=roms[sha].read_bytes();offset=origin_offset if sha==origin_sha else unique_offset(target,raw)
  if target[offset:offset+LENGTH]!=raw:raise ValueError(f'footprint mismatch: {rid}')
  report={'schema_version':1,'target':{'release':rid,'sha256':sha},'asset':{'name':'Footprints','source_offset':offset,'source_length':LENGTH,'source_sha256':raw_hash,'format':'game-boy-1bpp-8x8-tiles','tile_count':1024,'footprint_slots':SLOTS,'tiles_per_footprint':4},'outputs':[{'path':png_path.as_posix(),'sha256':digest(png),'width':256,'height':1024,'scale':2},{'path':layout_path.as_posix(),'sha256':file_hash(root/layout_path)}],'origin_reference':sha==origin_sha,'naming_basis':{'repository':reference_repository,'commit':reference_commit,'path':'gfx/footprints.asm','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};path=Path(f'analysis/{rid}-footprints.json');write_json(root/path,report);outputs.append(path);records.append({'id':rid,'language':row['language'],'revision':int(row['revision']),'sha256':sha,'origin_reference':sha==origin_sha,'evidence':path.as_posix(),'source_offset':offset})
 summary={'schema_version':1,'game':game,'asset':'Footprints','origin_reference':origin_release,'release_count':len(records),'source_sha256':raw_hash,'png':png_path.as_posix(),'layout':layout_path.as_posix(),'releases':records,'raw_rom_bytes_included':False};summary_path=Path('analysis/footprints-summary.json');write_json(root/summary_path,summary);outputs.append(summary_path)
 research=Path('research/footprints.md');languages=', '.join(dict.fromkeys(x['language']for x in records));(root/research).write_text(f"# {game} Pokémon footprints\n\nThe Japanese release `{origin_release}` is the origin reference. The complete 8,192-byte footprint table is byte-identical in all {len(records)} verified releases ({languages}), including Korean where officially available. It contains 256 four-tile slots: 251 species and five unused slots.\n\nThe ROM range is rendered as `graphics/pokemon/footprints-atlas.png`; `footprints-atlas.json` maps every numbered slot to logical and scaled PNG rectangles. Reports retain release identities, offsets, hashes, and provenance without publishing raw ROM bytes. Naming and storage order follow `{reference_repository}` at `{reference_commit}`, `gfx/footprints.asm`.\n",encoding='utf-8',newline='\n');outputs.append(research)
 test=Path('tests/test_footprints.py');outputs.append(test);missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError('missing output(s): '+', '.join(missing))
 manifest={'schema_version':1,'game':game,'asset':'Footprints','origin_reference':origin_release,'release_count':len(records),'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/extract_gen2_footprints.py','tool_sha256':file_hash(Path(__file__))},'outputs':[{'path':p.as_posix(),'sha256':file_hash(root/p)}for p in outputs],'raw_rom_bytes_included':False};write_json(root/'manifests/footprints.json',manifest)
 return summary
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--rom-dir',type=Path,required=True);p.add_argument('--origin-release',required=True);p.add_argument('--origin-offset',type=lambda x:int(x,0),required=True);p.add_argument('--game',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.origin_release,a.origin_offset,a.game,a.reference_repository,a.reference_commit)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
