#!/usr/bin/env python3
"""Measure fixed GBA ROM regions without retaining ROM bytes."""
from __future__ import annotations
import argparse,hashlib,json,math,struct
from collections import Counter
from pathlib import Path

def entropy(data:bytes)->float:
 if not data:return 0.0
 counts=Counter(data);n=len(data)
 return -sum((count/n)*math.log2(count/n) for count in counts.values())

def analyze_bytes(data:bytes,region_size:int=0x100000)->dict:
 if region_size<=0:raise ValueError("region size must be positive")
 if not data or len(data)%region_size:raise ValueError("ROM size must be a nonzero multiple of region size")
 regions=[]
 for index,start in enumerate(range(0,len(data),region_size)):
  chunk=data[start:start+region_size];words=struct.iter_unpack("<I",chunk[:len(chunk)//4*4]);rom_ptr=thumb_ptr=arm_branch=0
  for (word,) in words:
   if 0x08000000<=word<0x0A000000:
    rom_ptr+=1;thumb_ptr+=word&1
   if word>>24 in range(0xEA,0xEC):arm_branch+=1
  uniform=len(set(chunk))==1;fill=chunk[0] if uniform else None
  classification="header-and-entry" if index==0 else ("padding" if fill in (0,0xff) else "unclassified")
  regions.append({"region":index,"file_start":start,"file_end":start+len(chunk)-1,"gba_start":0x08000000+start,"gba_end":0x08000000+start+len(chunk)-1,"size":len(chunk),"sha256":hashlib.sha256(chunk).hexdigest(),"entropy":round(entropy(chunk),6),"unique_bytes":len(set(chunk)),"zero_bytes":chunk.count(0),"ff_bytes":chunk.count(0xff),"rom_pointer_words":rom_ptr,"thumb_pointer_words":thumb_ptr,"arm_branch_words":arm_branch,"classification":classification,"status":"measured","confidence":"high" if classification!="unclassified" else "low"})
 return {"schema_version":1,"size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"region_size":region_size,"region_count":len(regions),"regions":regions}

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("path",type=Path);p.add_argument("--region-size",type=lambda x:int(x,0),default=0x100000);p.add_argument("--json-output",type=Path);a=p.parse_args()
 try:r=analyze_bytes(a.path.read_bytes(),a.region_size)
 except (OSError,ValueError) as e:p.error(str(e))
 text=json.dumps(r,ensure_ascii=True,indent=2)+"\n"
 if a.json_output:a.json_output.write_text(text,encoding="utf-8",newline="\n")
 else:print(text,end="")
 return 0
if __name__=="__main__":raise SystemExit(main())
