import importlib.util,struct,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'extract_gba_lz77_4bpp.py';S=importlib.util.spec_from_file_location('gba_lz',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_literals_and_overlapping_lookback(self):
  stream=bytes([0x10,32,0,0,0])+bytes(range(8))+bytes([0x80,0xf0,7])+bytes(range(6))
  raw,used=M.decompress(stream);self.assertEqual(raw,bytes(range(8))+bytes(range(8))*2+bytes(range(2))+bytes(range(6)));self.assertEqual(used,22)
 def test_render_shape_and_nibble_order(self):
  raw=bytes([0x10])+bytes(31);png=M.render(raw,1,1);self.assertEqual(struct.unpack('>II',png[16:24]),(8,8));self.assertEqual(png,M.render(raw,1,1))
 def test_jasc_palette_render_and_report(self):
  palette=b'JASC-PAL\n0100\n16\n'+b'\n'.join(f'{n} {n} {n}'.encode() for n in range(16))+b'\n'
  colors=M.parse_jasc_palette(palette);self.assertEqual(colors[15],(15,15,15))
  png=M.render(bytes([0x10])+bytes(31),1,1,colors);self.assertEqual(png[25],2)
  stream=bytes([0x10,32,0,0,0])+bytes(32)+bytes(4);png,report=M.extract(stream,0,1,palette_bytes=palette);self.assertEqual(report['palette'],'jasc-pal');self.assertIn('palette_sha256',report)
  with self.assertRaises(ValueError):M.parse_jasc_palette(b'bad')
 def test_hash_gate_and_publication_report(self):
  stream=bytes([0x10,32,0,0,0])+bytes(32)+bytes(4);import hashlib
  png,report=M.extract(stream,0,1,hashlib.sha256(stream).hexdigest());self.assertEqual(report['decompressed_length'],32);self.assertFalse(report['raw_rom_bytes_included']);self.assertNotIn('decompressed_bytes',report);self.assertEqual(report['png_sha256'],hashlib.sha256(png).hexdigest())
  with self.assertRaises(ValueError):M.extract(stream,0,1,'0'*64)
 def test_invalid_streams(self):
  for stream in (b'',bytes([0x11,0,0,0]),bytes([0x10,1,0,0,0x80,0,0])):
   with self.assertRaises(ValueError):M.decompress(stream)
if __name__=='__main__':unittest.main()
