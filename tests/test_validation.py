import os
import sys
import unittest
import importlib

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)


def read(path):
    with open(os.path.join(BASE_DIR, path), "r", encoding="utf-8") as handle:
        return handle.read()


class TestFortiClientVPN(unittest.TestCase):
    def test_vpn_gui_imports(self):
        importlib.import_module("vpn-gui")

    def test_engine_and_config_import(self):
        importlib.import_module("vpn_engine")
        importlib.import_module("vpn_config")

    # ------------------------------------------------------------- arquivos
    def test_config_example_exists(self):
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "config", "forti.conf.example")))

    def test_config_example_has_psk(self):
        self.assertIn("secrets", read("config/forti.conf.example"))

    def test_icon_files_exist(self):
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "icon.png")))
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "icon.ico")))

    def test_desktop_file_exists(self):
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "assets", "forticlient-vpn.desktop")))

    def test_debian_control_exists(self):
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "debian", "control")))

    def test_debian_control_dependencies(self):
        self.assertIn("strongswan", read("debian/control"))

    def test_readme_has_both_platforms(self):
        content = read("README.md")
        self.assertIn("Windows", content)
        self.assertIn("Linux", content)

    def test_gitignore_has_dist(self):
        content = read(".gitignore")
        self.assertIn("dist/", content)
        self.assertIn("build/output", content)
        self.assertIn("vendor/windows/*.exe", content)

    # --------------------------------------------------------- build scripts
    def test_build_deb_script_exists(self):
        path = os.path.join(BASE_DIR, "build", "build_deb.sh")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.access(path, os.X_OK))

    def test_build_windows_script_exists(self):
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "build", "build_windows.bat")))

    def test_pyinstaller_spec_exists(self):
        self.assertTrue(os.path.exists(os.path.join(BASE_DIR, "build", "FortiClient-VPN.spec")))

    def test_pyinstaller_spec_has_no_forced_uac(self):
        """Elevar a GUI inteira foi a causa de conflitos no Windows."""
        self.assertNotIn("uac_admin=True", read("build/FortiClient-VPN.spec").replace(" ", ""))

    def test_windows_build_does_not_delete_itself(self):
        """O .bat rodava 'rmdir /s /q build' e apagava o proprio .spec."""
        content = read("build/build_windows.bat").lower()
        self.assertNotIn("rmdir /s /q build\n", content)
        self.assertNotIn("if exist build rmdir", content)

    def test_strongswan_cross_build_script_exists(self):
        path = os.path.join(BASE_DIR, "build", "build_strongswan_windows.sh")
        self.assertTrue(os.path.exists(path))

    def test_one_command_installer_script_exists(self):
        """O usuário não deve precisar preparar nada à mão."""
        path = os.path.join(BASE_DIR, "build", "preparar_instalador_windows.sh")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(os.access(path, os.X_OK))
        content = read("build/preparar_instalador_windows.sh")
        self.assertIn("ISCC", content)
        self.assertIn("wine", content)

    def test_ci_builds_the_installer(self):
        """Sem build local: o CI gera o instalador e publica como artefato."""
        path = os.path.join(BASE_DIR, ".github", "workflows", "build.yml")
        self.assertTrue(os.path.exists(path), "workflow .github/workflows/build.yml ausente")
        content = read(".github/workflows/build.yml")
        self.assertIn("msys2", content.lower())
        self.assertIn("ISCC", content)
        self.assertIn("upload-artifact", content)
        self.assertIn("windows-latest", content)

    # -------------------------------------------------------------- motor
    def test_no_native_windows_vpn_code(self):
        """IKEv2 nativo do Windows nao suporta PSK: nao pode voltar."""
        content = read("vpn-gui.py") + read("vpn_engine.py")
        self.assertNotIn("Add-VpnConnection -Name", content)
        self.assertNotIn("rasdial", content)

    def test_no_forticlient_backend(self):
        """O app nao pode depender do FortiClient nem de CLIs inexistentes."""
        content = read("vpn-gui.py") + read("vpn_engine.py")
        self.assertNotIn("fortivpn.exe", content)
        self.assertNotIn("fortissl", content)
        self.assertNotIn("FortiSSLVPNclient", content)
        # A unica mencao aceitavel e a limpeza dos residuos antigos.
        self.assertNotIn("configure_forticlient_tunnel", content)
        self.assertNotIn("find_forticlient", content)

    def test_engine_uses_swanctl(self):
        content = read("vpn_engine.py")
        self.assertIn("swanctl", content)
        self.assertIn("charon-svc.exe", content)
        self.assertIn("IKEEXT", content)

    def test_psk_field_in_gui(self):
        self.assertIn("entry_psk", read("vpn-gui.py"))

    def test_dpapi_functions_exist(self):
        content = read("vpn_config.py")
        self.assertIn("dpapi_encrypt", content)
        self.assertIn("dpapi_decrypt", content)

    def test_cleanup_of_previous_artifacts(self):
        content = read("vpn_engine.py")
        self.assertIn("cleanup_conflicts", content)
        self.assertIn("FortiClient-VPN", content)

    def test_packaging_ships_all_modules(self):
        """Empacotar so o vpn-gui.py quebra o app (importa os outros modulos)."""
        for path in ("build/build_deb.sh", "install.sh"):
            content = read(path)
            for module in ("vpn-gui.py", "vpn_engine.py", "vpn_config.py"):
                self.assertIn(module, content, "%s nao inclui %s" % (path, module))

    # ------------------------------------------------------------ sudoers
    def test_sudoers_allows_status_query(self):
        """Sem --list-sas no sudoers o status nunca funciona no Linux."""
        for path in ("install.sh", "debian/postinst"):
            self.assertIn("swanctl --list-sas", read(path), path)


if __name__ == "__main__":
    unittest.main()
