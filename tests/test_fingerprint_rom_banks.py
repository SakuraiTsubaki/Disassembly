from __future__ import annotations
import csv,importlib.util,io,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=importlib.util.spec_from_file_location("fingerprint_rom_banks",ROOT/"tools"/"fingerprint_rom_banks.py");m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class FingerprintRomBanksTests(unittest.TestCase):
 def test_bank_boundaries_and_classification(self):
  data=bytes(range(256))*64+bytes([0xFF])*0x4000;r=m.fingerprint_bytes(data);self.assertEqual(r["bank_count"],2);self.assertEqual((r["banks"][0]["cpu_start"],r["banks"][0]["cpu_end"]),(0,0x3FFF));self.assertEqual((r["banks"][1]["cpu_start"],r["banks"][1]["cpu_end"]),(0x4000,0x7FFF));self.assertEqual(r["banks"][1]["classification"],"padding");self.assertEqual(r["banks"][0]["entropy"],8.0)
 def test_csv_contains_bank_hashes(self):
  r=m.fingerprint_bytes(bytes(0x8000));
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/"banks.csv";m.write_csv(p,r);rows=list(csv.DictReader(io.StringIO(p.read_text(encoding="utf-8"))));self.assertEqual(len(rows),2);self.assertIn("bank_sha256=",rows[0]["notes"]);self.assertEqual(rows[0]["source_sha256"],r["sha256"])
 def test_misaligned_input_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"multiple"):m.fingerprint_bytes(bytes(0x4001))
 def test_invalid_bank_size_is_rejected(self):
  with self.assertRaisesRegex(ValueError,"positive"):m.fingerprint_bytes(b"x",0)
if __name__=="__main__":unittest.main()

