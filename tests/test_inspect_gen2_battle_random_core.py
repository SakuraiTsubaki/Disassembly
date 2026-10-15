import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "inspect_gen2_battle_random_core", ROOT / "tools/inspect_gen2_battle_random_core.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def routine(random=0x305E, link_mode=0xD03C, count=0xCBB7, seeds=0xD0D5):
    return bytes((
        0xFA,link_mode&0xff,link_mode>>8,0xA7,0xCA,random&0xff,random>>8,
        0xE5,0xC5,0xFA,count&0xff,count>>8,0x4F,0x06,0x00,
        0x21,seeds&0xff,seeds>>8,0x09,0x3C,0xEA,count&0xff,count>>8,
        0xFE,0x09,0x7E,0xC1,0xE1,0xD8,0xE5,0xC5,0xF5,0xAF,
        0xEA,count&0xff,count>>8,0x21,seeds&0xff,seeds>>8,0x06,0x0A,
        0x7E,0x4F,0x87,0x87,0x81,0x3C,0x22,0x05,0x20,0xF6,
        0xF1,0xC1,0xE1,0xC9,
    ))


class InspectGen2BattleRandomCoreTests(unittest.TestCase):
    def test_extracts_state_and_control_flow(self):
        data=bytearray(0x50000);data[0x3EC31:0x3EC31+MODULE.LENGTH]=routine()
        match=MODULE.inspect(bytes(data),0x3EC31,0x305E)
        self.assertEqual((match["bank"],match["address"]),(15,0x6C31))
        self.assertEqual(match["state"],{"wLinkMode":0xD03C,"wLinkBattleRNCount":0xCBB7,"wLinkBattleRNs":0xD0D5,"stream_length":10})
        self.assertEqual(match["control_flow"]["non_link_jump"],{"bank":0,"address":0x305E})
        self.assertEqual(match["prng"]["formula"],"seed = (seed * 5 + 1) mod 256")

    def test_rejects_wrong_random_target(self):
        self.assertIsNone(MODULE.inspect(routine(),0,0x305F))

    def test_rejects_mismatched_state_operands(self):
        data=bytearray(routine());data[34]^=1
        self.assertIsNone(MODULE.inspect(bytes(data),0,0x305E))

    def test_rejects_broken_loop_back_edge(self):
        data=bytearray(routine());data[50]=0xF5
        self.assertIsNone(MODULE.inspect(bytes(data),0,0x305E))


if __name__ == "__main__":
    unittest.main()
