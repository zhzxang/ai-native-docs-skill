"""Observable inventory behavior, using disposable data files."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from inventory_cli.cli import main
from inventory_cli import store


class InventoryTests(unittest.TestCase):
    def test_add_accumulates_quantity_and_remove_deletes_item(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--data", str(path), "add", "Pencil", "3"]), 0)
                self.assertEqual(main(["--data", str(path), "add", "Pencil", "2"]), 0)
                self.assertEqual(store.load(path), {"Pencil": 5})
                self.assertEqual(main(["--data", str(path), "remove", "Pencil"]), 0)
            self.assertEqual(store.load(path), {})

    def test_list_preserves_data_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inventory.json"
            store.save(path, {"Pencil": 3})
            before = path.read_bytes()
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--data", str(path), "list"]), 0)
            self.assertEqual(output.getvalue(), "Pencil\t3\n")
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

