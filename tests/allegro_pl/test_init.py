from unittest import TestCase

import allegro_pl
import toml


class test_init(TestCase):

    def test_version_matches(self):
        self.assertEqual(get_project_version(), allegro_pl.__version__)


def get_project_version():
    return toml.load('pyproject.toml')['tool']['poetry']['version']
