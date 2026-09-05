import os
import tempfile
import unittest
from unittest.mock import patch

from src.utils.utils import load_dotenv


class DotenvTests(unittest.TestCase):
    def test_load_dotenv_does_not_override_existing_environment(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8") as file:
            file.write("EXISTING_VALUE=from-file\nNEW_VALUE=loaded\n")
            file.flush()
            with patch.dict(os.environ, {"EXISTING_VALUE": "from-env"}, clear=False):
                os.environ.pop("NEW_VALUE", None)
                loaded = load_dotenv(file.name)
                self.assertEqual(loaded, 1)
                self.assertEqual(os.environ["EXISTING_VALUE"], "from-env")
                self.assertEqual(os.environ["NEW_VALUE"], "loaded")
                os.environ.pop("NEW_VALUE", None)


if __name__ == "__main__":
    unittest.main()
