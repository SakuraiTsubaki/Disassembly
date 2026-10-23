#!/usr/bin/env python3
"""Extract and verify the Generation II Unown font across official releases."""
from __future__ import annotations
import argparse,csv,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import extract_gb_2bpp

LENGTH=27*16
def digest(data):return hashlib.sha256(data).hexdigest()
def file_hash(path):return digest(path.read_bytes())
def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def unique_offset(data,signature):
 found=[];start=0
 while True:
  offset=data.find(signature,start)
  if offset<0:break
  found.append(offset);start=offset+1
 if len(found)!=1:raise ValueError(f'expected one Unown font, found {len(found)}')
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
 origin_data=roms[origin_sha].read_bytes();raw=origin_data[origin_offset:origin_offset+LENGTH]
 if len(raw)!=LENGTH:raise ValueError('origin range leaves ROM')
 if any(raw[i]!=raw[i+1] for i in range(0,LENGTH,2)):raise ValueError('font is not the expected monochrome 2bpp representation')
 raw_hash=digest(raw);png=extract_gb_2bpp.render(raw,3);png_path=Path('graphics/font/unown-font.png');(root/png_path).parent.mkdir(parents=True,exist_ok=True);(root/png_path).write_bytes(png)
 outputs=[png_path];records=[]
 for row in rows:
  sha=row['sha256'];rid=row['id']
  if sha not in roms:raise ValueError(f'missing release ROM: {rid}')
  data=roms[sha].read_bytes();offset=origin_offset if sha==origin_sha else unique_offset(data,raw)
  if data[offset:offset+LENGTH]!=raw:raise ValueError(f'font mismatch: {rid}')
  report={'schema_version':1,'target':{'release':rid,'sha256':sha},'asset':{'name':'UnownFont','source_offset':offset,'source_length':LENGTH,'source_sha256':raw_hash,'format':'game-boy-2bpp-8x8-tiles','tile_count':27,'tiles_per_row':3,'monochrome_planes_identical':True},'output':{'path':png_path.as_posix(),'sha256':digest(png),'width':48,'height':144,'scale':2},'origin_reference':sha==origin_sha,'naming_basis':{'repository':reference_repository,'commit':reference_commit,'path':'gfx/font.asm','asset_path':'gfx/font/unown_font.png','raw_rom_bytes_published':False},'raw_rom_bytes_included':False};path=Path(f'analysis/{rid}-unown-font.json');write_json(root/path,report);outputs.append(path);records.append({'id':rid,'language':row['language'],'revision':int(row['revision']),'sha256':sha,'origin_reference':sha==origin_sha,'evidence':path.as_posix(),'source_offset':offset})
 summary={'schema_version':1,'game':game,'asset':'UnownFont','origin_reference':origin_release,'release_count':len(records),'source_sha256':raw_hash,'png':png_path.as_posix(),'png_sha256':digest(png),'releases':records,'raw_rom_bytes_included':False};summary_path=Path('analysis/unown-font-summary.json');write_json(root/summary_path,summary);outputs.append(summary_path)
 report_path=Path('research/unown-font.md');languages=', '.join(dict.fromkeys(x['language'] for x in records));(root/report_path).write_text(f"# {game} Unown font\n\nThe Japanese release `{origin_release}` is the origin reference. Its 27 uncompressed 2bpp tiles are byte-identical in all {len(records)} verified releases ({languages}), including the official Korean release where available. The two bitplanes are identical, producing a monochrome glyph set.\n\n`graphics/font/unown-font.png` is regenerated directly from the local ROM range. Per-release reports preserve ROM identity, offsets, source and PNG hashes, while no raw ROM bytes are published. Naming is corroborated by `{reference_repository}` at `{reference_commit}`, `gfx/font.asm`.\n",encoding='utf-8',newline='\n');outputs.append(report_path)
 test_path=Path('tests/test_unown_font.py');outputs.append(test_path);missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError('missing output(s): '+', '.join(missing))
 manifest={'schema_version':1,'game':game,'asset':'UnownFont','origin_reference':origin_release,'release_count':len(records),'generator':{'repository':'SakuraiTsubaki/Disassembly','tool':'tools/extract_gen2_unown_font.py','tool_sha256':file_hash(Path(__file__))},'outputs':[{'path':p.as_posix(),'sha256':file_hash(root/p)}for p in outputs],'raw_rom_bytes_included':False};write_json(root/'manifests/unown-font.json',manifest)
 return summary
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--rom-dir',type=Path,required=True);p.add_argument('--origin-release',required=True);p.add_argument('--origin-offset',type=lambda x:int(x,0),required=True);p.add_argument('--game',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.origin_release,a.origin_offset,a.game,a.reference_repository,a.reference_commit)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
