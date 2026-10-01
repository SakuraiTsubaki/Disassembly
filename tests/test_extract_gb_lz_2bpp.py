import importlib.util,struct,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'extract_gb_lz_2bpp.py';S=importlib.util.spec_from_file_location('lz',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_sequences_and_short_repeat(self):
  raw,used=M.decompress(bytes([0x02,1,2,3,0x21,4,0x43,5,6,0x63,0x83,0x8c,0xff]));self.assertEqual(raw,bytes([1,2,3,4,4,5,6,5,6,0,0,0,0,1,2,3,4]));self.assertEqual(used,13)
 def test_long_literal_and_render(self):
  stream=bytes([0xe0,15])+bytes(16)+bytes([0xff]);raw,_=M.decompress(stream);self.assertEqual(len(raw),16);png=M.render(raw,1);self.assertEqual(struct.unpack('>II',png[16:24]),(16,16))
 def test_bit_flip_and_reverse_lookbacks(self):
  stream=bytes([0x03,0x0f,0xf0,0xaa,0x55,0xa3,0x83,0xc3,0x00,0x03,0xff])
  raw,_=M.decompress(stream)
  self.assertEqual(raw,bytes([0x0f,0xf0,0xaa,0x55,0xf0,0x0f,0x55,0xaa,0x55,0xaa,0xf0,0x0f]))
 def test_long_repeat_can_overlap_output(self):
  seed=bytes(range(16));stream=bytes([0x0f])+seed+bytes([0xf0,32,0x8f,0xff])
  raw,_=M.decompress(stream)
  self.assertEqual(raw,seed+bytes(range(16))*2+bytes([0]))
 def test_bad_lookback(self):
  with self.assertRaises(ValueError):M.decompress(bytes([0x80,0x80,0xff]))
if __name__=='__main__':unittest.main()

