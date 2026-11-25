from pathlib import Path
import sys
import unittest
from unittest.mock import DEFAULT, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import kind_lab


class KindImageImport(unittest.TestCase):
    def test_helm_values_reference_the_exact_images_loaded_into_kind(self):
        identifiers = ["sha256:" + digit * 64 for digit in "abcd"]
        image_names = [
            "vllm-ops-fixture",
            "vllm-ops-postgres",
            "verstak-agent",
            "verifine-slm",
        ]
        pinned = [f"{name}:{image_id[7:]}" for name, image_id in zip(image_names, identifiers)]

        def docker_command(*args, **kwargs):
            if args[:3] == ("docker", "image", "inspect"):
                return identifiers[image_names.index(args[-1].removesuffix(":local"))] + "\n"
            return None

        with patch.object(kind_lab, "run", side_effect=docker_command) as run:
            values = kind_lab.load_local_images()

        keys = ("backend.fixtureImage", "images.postgres", "images.verstak", "images.verifine")
        self.assertEqual(values, dict(zip(keys, pinned)))
        commands = [call.args for call in run.call_args_list]
        for image_id, image in zip(identifiers, pinned):
            self.assertIn(("docker", "image", "tag", image_id, image), commands)
        save = next(args for args in commands if args[:3] == ("docker", "image", "save"))
        self.assertEqual(list(save[-4:]), pinned)
        self.assertIn("--platform", save)
        self.assertTrue(any(args[:3] == ("kind", "load", "image-archive") for args in commands))


    def test_skip_import_reuses_only_previous_image_values(self):
        with patch.object(kind_lab, "helm", side_effect=[
            '[{"name":"ops"}]',
            '{"images":{"postgres":"postgres:old"},"networkPolicy":{"enabled":false}}',
        ]):
            self.assertEqual(kind_lab.deployed_images(), {"images.postgres": "postgres:old"})

    def test_postgres_rebuild_migrates_the_database_after_helm_readiness(self):
        with patch.multiple(kind_lab, helm=DEFAULT, kubectl=DEFAULT) as tools:
            commands = Mock()
            commands.attach_mock(tools["helm"], "helm")
            commands.attach_mock(tools["kubectl"], "kubectl")
            kind_lab.deploy_app({"images.postgres": "postgres:new"}, {"images.postgres": "postgres:old"})

        self.assertEqual([call[0] for call in commands.mock_calls], ["helm", "kubectl", "helm"])
        self.assertEqual(commands.mock_calls[1].args[-3:], ("alembic", "upgrade", "head"))
