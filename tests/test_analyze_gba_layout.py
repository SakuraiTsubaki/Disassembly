from __future__ import annotations
import importlib.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("analyze_gba_layout",ROOT/"tools"/"analyze_gba_layout.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class AnalyzeGbaLayoutTests(unittest.TestCase):
 def test_regions_and_conservative_classification(self):
  first=bytearray(0x100);first[4:8]=(0x08001235).to_bytes(4,"little");first[8:12]=(0xEA000000).to_bytes(4,"little");r=m.analyze_bytes(bytes(first)+bytes([0xff])*0x100,0x100);self.assertEqual(r["region_count"],2);self.assertEqual(r["regions"][0]["classification"],"header-and-entry");self.assertEqual(r["regions"][0]["rom_pointer_words"],1);self.assertEqual(r["regions"][0]["thumb_pointer_words"],1);self.assertEqual(r["regions"][0]["arm_branch_words"],1);self.assertEqual(r["regions"][1]["classification"],"padding")
 def test_misaligned_input_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"multiple"):m.analyze_bytes(b"x"*257,0x100)
 def test_invalid_region_size_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"positive"):m.analyze_bytes(b"x",0)
if __name__=="__main__":unittest.main()
