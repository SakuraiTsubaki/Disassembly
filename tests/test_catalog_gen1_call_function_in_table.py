import unittest

from tools import catalog_gen1_call_function_in_table as table


class CallFunctionInTableCatalogToolTests(unittest.TestCase):
    def test_locate_validates_return_address(self):
        start = 3
        routine = table.PREFIX + (start + table.RETURN_OFFSET).to_bytes(2, "little") + table.SUFFIX
        found = table.locate(b"\0" * start + routine)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["return_address"], start + table.RETURN_OFFSET)

    def test_rejects_wrong_return_address(self):
        routine = table.PREFIX + bytes((0, 0)) + table.SUFFIX
        self.assertEqual(table.locate(b"\0" * 3 + routine), [])

    def test_table_target(self):
        self.assertEqual(table.table_target(bytes.fromhex("34127856"), 1), 0x5678)

    def test_rejects_wrapping_or_missing_index(self):
        with self.assertRaises(ValueError):
            table.table_target(b"\0\0", 128)
        with self.assertRaises(ValueError):
            table.table_target(b"\0\0", 1)


if __name__ == "__main__":
    unittest.main()
