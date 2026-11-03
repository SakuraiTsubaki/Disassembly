#!/usr/bin/env python3
"""Catalog GetFarByte and GetFarWord across Generation II release sets."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common
PROFILES={
 "gs":{"repository":"pret/pokegold","commit":"ef0201d8daf47e8b3ea1518eacf890f37d4cd5e8","path":"home/copy.asm"},
 "crystal":{"repository":"pret/pokecrystal","commit":"3bc8daa4173e96a7f4011dad3922eb6fa5dad5c6","path":"home/copy.asm"}}
LENGTHS={"gs":{"GetFarByte":20,"GetFarWord":16},"crystal":{"GetFarByte":16,"GetFarWord":14}}
def decode_gs(data:bytes,offset:int)->dict|None:
 b=data[offset:offset+20];w=data[offset+20:offset+36]
 if len(b)!=20 or not(b[0]==0xEA and b[3]==0xF0 and b[5]==0xF5 and b[6]==0xFA and b[9]==0xD7 and b[10]==0x7E and b[11]==0xEA and b[14]==0xF1 and b[15]==0xD7 and b[16]==0xFA and b[19]==0xC9):return None
 if b[1:3]!=b[7:9] or b[12:14]!=b[17:19]:return None
 if len(w)!=16 or not(w[0]==0xEA and w[3]==0xF0 and w[5]==0xF5 and w[6]==0xFA and w[9]==0xD7 and w[10:13]==bytes.fromhex("2a666f") and w[13:]==bytes.fromhex("f1d7c9")):return None
 if w[1:3]!=w[7:9] or w[1:3]!=b[1:3] or w[4]!=b[4]:return None
 return {"GetFarByte":{"length":20,"code":b,"temporary_bank_storage":f"0x{int.from_bytes(b[1:3],'little'):04X}","rom_bank_shadow":f"0xFF{b[4]:02X}","far_byte_storage":f"0x{int.from_bytes(b[12:14],'little'):04X}"},"GetFarWord":{"length":16,"code":w,"temporary_bank_storage":f"0x{int.from_bytes(w[1:3],'little'):04X}","rom_bank_shadow":f"0xFF{w[4]:02X}"}}
def decode_crystal(data:bytes,offset:int)->dict|None:
 b=data[offset:offset+16];w=data[offset+16:offset+30]
 if len(b)!=16 or not(b[0]==0xE0 and b[2]==0xF0 and b[4]==0xF5 and b[5]==0xF0 and b[7]==0xD7 and b[8]==0x7E and b[9]==0xE0 and b[11]==0xF1 and b[12]==0xD7 and b[13]==0xF0 and b[15]==0xC9):return None
 if b[1]!=b[6] or b[1]!=b[10] or b[1]!=b[14]:return None
 if len(w)!=14 or not(w[0]==0xE0 and w[2]==0xF0 and w[4]==0xF5 and w[5]==0xF0 and w[7]==0xD7 and w[8:11]==bytes.fromhex("2a666f") and w[11:]==bytes.fromhex("f1d7c9")):return None
 if w[1]!=w[6] or w[1]!=b[1] or w[3]!=b[3]:return None
 return {"GetFarByte":{"length":16,"code":b,"temporary_bank_storage":f"0xFF{b[1]:02X}","rom_bank_shadow":f"0xFF{b[3]:02X}","far_byte_storage":f"0xFF{b[10]:02X}"},"GetFarWord":{"length":14,"code":w,"temporary_bank_storage":f"0xFF{w[1]:02X}","rom_bank_shadow":f"0xFF{w[3]:02X}"}}
def locate(data:bytes,profile:str)->list[tuple[int,dict]]:
 decoder=decode_gs if profile=="gs" else decode_crystal
 return [(o,f) for o in range(0x100,min(0x4000,len(data))-36) if (f:=decoder(data,o)) is not None]
def source_text(profile:str)->str:
 temp="wTempBank" if profile=="gs" else "hTempBank";far="wFarByte" if profile=="gs" else "hFarByte";store="ld" if profile=="gs" else "ldh"
 return f"""SECTION "Far Access Reconstruction", ROM0

GetFarByte::
    {store} [{temp}], a
    ldh a, [hROMBank]
    push af
    {store} a, [{temp}]
    rst Bankswitch
    ld a, [hl]
    {store} [{far}], a
    pop af
    rst Bankswitch
    {store} a, [{far}]
    ret

GetFarWord::
    {store} [{temp}], a
    ldh a, [hROMBank]
    push af
    {store} a, [{temp}]
    rst Bankswitch
    ld a, [hli]
    ld h, [hl]
    ld l, a
    pop af
    rst Bankswitch
    ret
"""
def build(root:Path,rom_dir:Path,game:str,profile:str)->dict:
 naming=PROFILES[profile];catalog_path,releases=common.load_releases(root);roms=common.rom_index(rom_dir);source_path=Path("src/far_access.asm");(root/source_path).write_text(source_text(profile),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing release ROM: {rid}")
  data=roms[sha256].read_bytes();matches=locate(data,profile)
  if len(matches)!=1:raise ValueError(f"expected one far-access suite in {rid}, found {len(matches)}")
  start,decoded=matches[0];functions={}
  cursor=start
  for name in ("GetFarByte","GetFarWord"):
   f=decoded[name];code=f.pop("code");functions[name]={"rom_offset":cursor,"bank":0,"address":cursor,"range_end_exclusive":cursor+f["length"],"code_sha256":common.digest(code),**f};cursor+=f["length"]
  dep_path=Path(f"analysis/{rid}-copy-bytes.json");dep=json.loads((root/dep_path).read_text(encoding="utf-8"))
  evidence={"schema_version":1,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"profile":profile,"functions":functions,"semantics":{"GetFarByte":"switch to bank A, read [HL], restore the previous ROM bank, return byte in A","GetFarWord":"switch to bank A, read little-endian [HL:HL+1], restore the previous ROM bank, return word in HL"},"cross_reference":{"copy_bytes":dep_path.as_posix(),"sha256":common.file_hash(root/dep_path),"get_far_byte_offset_from_copy_bytes_end":start-int(dep["function"]["range_end_exclusive"])},"naming_basis":naming,"raw_rom_bytes_included":False}
  language=release["language"] if release.get("language") else common.infer_language(rid)
  map_path=Path(f"analysis/{rid}-far-access.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":language,"revision":int(release.get("revision",0)),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"addresses":{n:f"0x{v['address']:04X}" for n,v in functions.items()},"evidence":map_path.as_posix()})
 summary={"schema_version":1,"game":game,"functions":["GetFarByte","GetFarWord"],"profile":profile,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/far-access-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));research_path=Path("research/far-access-reconstruction.md");(root/research_path).write_text(f"# {game} far-ROM access reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) independently verify adjacent GetFarByte and GetFarWord routines. Both save the current ROM bank, switch to the bank in A, read through HL, restore the previous bank, and return without publishing ROM bytes. The {profile} profile records its distinct temporary-storage convention.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_far_access_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
 common.write_json(root/"manifests/far-access-reconstruction.json",{"schema_version":1,"game":game,"functions":["GetFarByte","GetFarWord"],"profile":profile,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen2_far_access.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--profile",choices=sorted(PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.profile)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
