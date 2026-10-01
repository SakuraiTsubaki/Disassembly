import hashlib,importlib.util,struct,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'tools'/'extract_gba_lz77_8bpp.py';S=importlib.util.spec_from_file_location('gba_lz8',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)

class Tests(unittest.TestCase):
 def test_literal_stream_and_render(self):
  raw=bytes(range(64));stream=bytes([0x10,64,0,0])+b''.join(bytes([0])+raw[n:n+8] for n in range(0,64,8));decoded,used=M.decompress(stream);self.assertEqual(decoded,raw);self.assertEqual(used,len(stream));png=M.render(raw,1);self.assertEqual(struct.unpack('>II',png[16:24]),(8,8))
 def test_palette_and_report(self):
  palette=b'JASC-PAL\n0100\n256\n'+b'\n'.join(f'{n} {n} {n}'.encode() for n in range(256))+b'\n';colors=M.parse_jasc_palette(palette);self.assertEqual(len(colors),256)
  raw=bytes(64);stream=bytes([0x10,64,0,0])+b''.join(bytes([0])+raw[n:n+8] for n in range(0,64,8));png,report=M.extract(stream,0,1,hashlib.sha256(stream).hexdigest(),palette);self.assertEqual(png[25],2);self.assertEqual(report['format'],'gba-bios-lz77-to-8bpp-tiles');self.assertFalse(report['raw_rom_bytes_included'])
 def test_invalid_inputs(self):
  with self.assertRaises(ValueError):M.render(bytes(32),1)
  with self.assertRaises(ValueError):M.render(bytes(64),1,palette=[(0,0,0)]*16)
  with self.assertRaises(ValueError):M.parse_jasc_palette(b'bad')

if __name__=='__main__': unittest.main()
