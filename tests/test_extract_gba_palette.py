import hashlib,importlib.util,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'extract_gba_palette.py';S=importlib.util.spec_from_file_location('gba_pal',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_bgr555_endpoints_and_jasc(self):
  colors=M.decode(bytes([0,0,31,0,224,3,0,124,255,127]),0,5);self.assertEqual(colors,[(0,0,0),(255,0,0),(0,255,0),(0,0,255),(255,255,255)]);self.assertTrue(M.jasc(colors).startswith(b'JASC-PAL\n0100\n5\n'))
 def test_hash_gate_and_report(self):
  rom=bytes([31,0])*16;palette,report=M.extract(rom,0,16,hashlib.sha256(rom).hexdigest());self.assertEqual(report['color_count'],16);self.assertFalse(report['raw_rom_bytes_included']);self.assertEqual(report['palette_sha256'],hashlib.sha256(palette).hexdigest())
  with self.assertRaises(ValueError):M.extract(rom,0,16,'0'*64)
 def test_invalid_range(self):
  with self.assertRaises(ValueError):M.decode(b'\0\0',1,1)
  with self.assertRaises(ValueError):M.decode(b'\0\0',0,0)
if __name__=='__main__':unittest.main()
