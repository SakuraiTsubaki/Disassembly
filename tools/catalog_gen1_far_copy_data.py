#!/usr/bin/env python3
"""Reconstruct Generation I FarCopyData from the verified CopyData boundary."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import catalog_gen1_clear_screen as common
LENGTH=24
PROFILES={
 "classic":{"repository":"pret/pokered","commit":"af519899719f0754965776faac0e836a3b906e6d","path":"home/copy.asm"},
 "yellow":{"repository":"pret/pokeyellow","commit":"31b7c2ea2ba6c8c64ed083723fbaa8cbb74669cb","path":"home/copy.asm"}}
def decode_classic(data:bytes,copy_offset:int,copy_address:int)->dict|None:
 start=copy_offset-LENGTH
 if start<0:return None
 c=data[start:copy_offset]
 if len(c)!=LENGTH or not(c[0]==0xEA and c[3]==0xF0 and c[5]==0xF5 and c[6]==0xFA and c[9]==0xE0 and c[11]==0xEA and c[14]==0xCD and c[17]==0xF1 and c[18]==0xE0 and c[20]==0xEA and c[23]==0xC9):return None
 w0=c[1]|c[2]<<8;w1=c[7]|c[8]<<8;h0=c[4];h1=c[10];h2=c[19];r0=c[12]|c[13]<<8;r1=c[21]|c[22]<<8;target=c[15]|c[16]<<8
 if w0!=w1 or h0!=h1 or h0!=h2 or r0!=r1 or target!=copy_address:return None
 bank=start//0x4000;address=start if bank==0 else 0x4000+start%0x4000
 return {"rom_offset":start,"bank":bank,"address":address,"range_end_exclusive":copy_offset,"length":LENGTH,"code_sha256":common.digest(c),"wBuffer":f"0x{w0:04X}","hLoadedROMBank":f"0xFF{h0:02X}","rROMB":f"0x{r0:04X}","copy_data_address":f"0x{target:04X}"}
def decode_yellow(data:bytes,offset:int,copy_address:int)->dict|None:
 c=data[offset:offset+20]
 if len(c)!=20 or not(c[0]==0xEA and c[3]==0xF0 and c[5]==0xF5 and c[6]==0xFA and c[9]==0xCD and c[12]==0xCD and c[15]==0xF1 and c[16]==0xCD and c[19]==0xC9):return None
 w0=c[1]|c[2]<<8;w1=c[7]|c[8]<<8;switch0=c[10]|c[11]<<8;target=c[13]|c[14]<<8;switch1=c[17]|c[18]<<8
 if w0!=w1 or switch0!=switch1 or target!=copy_address:return None
 bank=offset//0x4000;address=offset if bank==0 else 0x4000+offset%0x4000
 return {"rom_offset":offset,"bank":bank,"address":address,"range_end_exclusive":offset+20,"length":20,"code_sha256":common.digest(c),"wFarCopyDataSavedROMBank":f"0x{w0:04X}","hLoadedROMBank":f"0xFF{c[4]:02X}","bankswitch_common_address":f"0x{switch0:04X}","copy_data_address":f"0x{target:04X}"}
def locate_yellow(data:bytes,copy_address:int)->list[dict]:
 return [f for o in range(min(0x4000,len(data))-19) if (f:=decode_yellow(data,o,copy_address)) is not None]
def decode(data:bytes,copy_offset:int,copy_address:int)->dict|None:
 return decode_classic(data,copy_offset,copy_address)
def source_text(profile_name:str)->str:
 if profile_name=="yellow":
  return """SECTION "FarCopyData Reconstruction", ROM0

FarCopyData::
    ld [wFarCopyDataSavedROMBank], a
    ldh a, [hLoadedROMBank]
    push af
    ld a, [wFarCopyDataSavedROMBank]
    call BankswitchCommon
    call CopyData
    pop af
    call BankswitchCommon
    ret
"""
 return """SECTION "FarCopyData Reconstruction", ROM0

FarCopyData::
    ld [wBuffer], a
    ldh a, [hLoadedROMBank]
    push af
    ld a, [wBuffer]
    ldh [hLoadedROMBank], a
    ld [rROMB], a
    call CopyData
    pop af
    ldh [hLoadedROMBank], a
    ld [rROMB], a
    ret
"""
def build(root:Path,rom_dir:Path,game:str,profile_name:str)->dict:
 profile=PROFILES[profile_name];catalog_path,releases=common.load_releases(root);roms=common.rom_index(rom_dir);source_path=Path("src/far_copy_data.asm");(root/source_path).write_text(source_text(profile_name),encoding="utf-8",newline="\n");maps=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing release ROM: {rid}")
  dep_path=Path(f"analysis/{rid}-copy-data.json");dep=json.loads((root/dep_path).read_text(encoding="utf-8"));copy=dep["function"];data=roms[sha256].read_bytes()
  if profile_name=="yellow":
   matches=locate_yellow(data,int(copy["address"]))
   if len(matches)!=1:raise ValueError(f"expected one Yellow FarCopyData in {rid}, found {len(matches)}")
   f=matches[0]
  else:
   f=decode_classic(data,int(copy["rom_offset"]),int(copy["address"]))
   if f is None:raise ValueError(f"FarCopyData boundary differs in {rid}")
  evidence={"schema_version":1,"target":{"release":rid,"sha256":sha256,"status":release.get("status","candidate")},"origin_reference":index==0,"function":{"name":"FarCopyData",**f},"semantics":{"source_bank":"A","source_address":"HL","destination_address":"DE","length":"BC","operation":"save the current ROM bank, switch to A, call CopyData, then restore the prior bank","preserves_previous_rom_bank":True},"cross_reference":{"copy_data":dep_path.as_posix(),"sha256":common.file_hash(root/dep_path)},"naming_basis":profile,"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-far-copy-data.json");common.write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release.get("language",common.infer_language(rid)),"revision":int(release.get("revision",0)),"status":release.get("status","candidate"),"sha256":sha256,"origin_reference":index==0,"address":f"0x{f['address']:04X}","saved_bank_storage":f.get("wBuffer",f.get("wFarCopyDataSavedROMBank")),"hLoadedROMBank":f["hLoadedROMBank"],"evidence":map_path.as_posix()})
 summary={"schema_version":1,"game":game,"function":"FarCopyData","profile":profile_name,"origin_reference":releases[0]["id"],"release_count":len(records),"source":source_path.as_posix(),"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/far-copy-data-summary.json");common.write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"] for x in records));length=20 if profile_name=="yellow" else 24;placement="through BankswitchCommon" if profile_name=="yellow" else "immediately before CopyData";research_path=Path("research/far-copy-data-reconstruction.md");(root/research_path).write_text(f"# {game} FarCopyData reconstruction\n\n{releases[0]['id']} is the Japanese origin reference. All {len(records)} cataloged releases ({languages}) verify the {length}-byte FarCopyData wrapper {placement}. The wrapper saves the active ROM bank, selects the source bank from A, delegates the BC-byte transfer, and restores the previous bank. Addresses and hashes are preserved without publishing ROM bytes.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_far_copy_data_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,research_path,test_path]
 if any(not(root/p).is_file() for p in outputs):raise ValueError("missing output")
 common.write_json(root/"manifests/far-copy-data-reconstruction.json",{"schema_version":1,"game":game,"function":"FarCopyData","profile":profile_name,"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Disassembly","tool":"tools/catalog_gen1_far_copy_data.py","tool_sha256":common.file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":common.file_hash(root/p)} for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--game",required=True);p.add_argument("--profile",choices=sorted(PROFILES),required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.game,a.profile)
 except(OSError,KeyError,ValueError,json.JSONDecodeError) as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
