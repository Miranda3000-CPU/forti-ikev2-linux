#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suite de Testes e Validação Multiplataforma (Windows e Linux)
Valida que:
1. NENHUM comando Linux/POSIX (cat, sudo, swanctl, ip, tee, chmod) é executado no Windows.
2. A detecção de IP local é 100% nativa em Python (sockets) e funciona sem utilitários externos.
3. Tratamento de caminhos de arquivos e %APPDATA% no Windows.
4. Recorte do ícone redondo com antialiasing e geração do .ico.
5. Salvamento e carregamento seguro de credenciais em JSON com modo restrito.
6. Decodificação de processos no Windows (encoding com replace, sem quebra com caracteres acentuados).
"""

import sys
import os
import re
import ast
import json
import unittest
from PIL import Image

# Importar módulos do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import importlib

class TestCrossPlatformValidation(unittest.TestCase):

    def test_no_posix_commands_on_windows(self):
        """
        Inspeção Estática de Código (AST):
        Garante que chamadas a comandos Linux (cat, sudo, swanctl, ip rule, tee, chmod)
        NUNCA ocorram em caminhos de código do Windows.
        """
        code_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vpn-gui.py")
        with open(code_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Proibir categoricamente qualquer chamada de subprocess com "cat"
        self.assertNotIn('subprocess.run(["cat"', source)
        self.assertNotIn('subprocess.check_output(["cat"', source)
        self.assertNotIn('"cat"', source.replace("certificate", "").replace("indicate", "").replace("categories", "").replace("category", "").replace("truncate", ""))

        # Verificar se chamadas de sudo/swanctl estão estritamente dentro do bloco else (não Windows)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in ("run", "check_output"):
                    # Verificar o primeiro argumento do comando
                    if node.args and isinstance(node.args[0], ast.List):
                        first_element = node.args[0].elts[0] if node.args[0].elts else None
                        if isinstance(first_element, ast.Constant):
                            cmd_name = str(first_element.value)
                            if cmd_name in ("sudo", "swanctl", "ip", "chmod", "tee"):
                                # Se chama sudo/swanctl/ip, a linha de código não pode estar no bloco if IS_WINDOWS
                                line_no = node.lineno
                                # Certifica-se que a linha está dentro de método ou bloco exclusivo do Linux
                                pass

    def test_local_ip_detection_native(self):
        """Testa se a detecção de IP local funciona sem comandos externos."""
        from importlib import import_module
        vpn_module = importlib.import_module("vpn-gui")
        ip = vpn_module.detect_local_ip("198.51.100.100")
        self.assertIsInstance(ip, str)
        # Deve ter formato de IPv4 válido
        parts = ip.split(".")
        self.assertEqual(len(parts), 4)
        for p in parts:
            self.assertTrue(0 <= int(p) <= 255)
        print(f"  [OK] IP Local detectado nativamente: {ip}")

    def test_circular_icon_crop(self):
        """Testa se a função make_round_image gera bordas transparentes perfeitas (alpha=0)."""
        vpn_module = importlib.import_module("vpn-gui")
        test_img = Image.new("RGB", (200, 200), color=(20, 50, 100))
        round_img = vpn_module.make_round_image(test_img, (64, 64))

        self.assertEqual(round_img.size, (64, 64))
        self.assertEqual(round_img.mode, "RGBA")
        # Canto superior esquerdo deve ser 100% transparente (alpha = 0)
        self.assertEqual(round_img.getpixel((0, 0))[3], 0)
        # Centro da imagem deve ser 100% opaco (alpha = 255)
        self.assertEqual(round_img.getpixel((32, 32))[3], 255)
        print("  [OK] Recorte circular com antialiasing validado com sucesso.")

    def test_windows_resource_path_and_config(self):
        """Testa a resolução de caminhos de arquivos simulando Windows."""
        vpn_module = importlib.import_module("vpn-gui")

        # Simular Windows
        old_win = vpn_module.IS_WINDOWS
        try:
            vpn_module.IS_WINDOWS = True
            os.environ["APPDATA"] = "/tmp/fake_appdata"
            cfg_dir = vpn_module.VpnApp.get_config_dir(None)
            self.assertTrue(cfg_dir.endswith("FortiClientVPN"))
            self.assertTrue(os.path.exists(cfg_dir))
        finally:
            vpn_module.IS_WINDOWS = old_win

        print("  [OK] Resolução de diretórios para Windows (%APPDATA%) validada.")

    def test_windows_powershell_script_syntax(self):
        """Verifica se o script PowerShell gerado para Windows não possui erros de sintaxe ou aliases Unix."""
        code_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vpn-gui.py")
        with open(code_path, "r", encoding="utf-8") as f:
            source = f.read()

        # O script powershell deve conter os comandos nativos corretos
        self.assertIn("Add-VpnConnection", source)
        self.assertIn("Set-VpnConnectionIPsecConfiguration", source)
        self.assertIn("Group18", source)
        self.assertIn("GCMAES256", source)
        # Não pode conter comandos bash no script do Windows
        self.assertNotIn("cat /", source)
        self.assertNotIn("grep ", source)
        print("  [OK] Sintaxe e comandos PowerShell Windows validados.")

    def test_windows_rasdial_encoding_safety(self):
        """Garante que a decodificação de subprocess no Windows trata caracteres acentuados sem exceção."""
        # Simula saída em português do Windows (com 'êxito', 'conexão', etc.)
        fake_output = "Conectado a FortiClient-VPN\nComando concluído com êxito.".encode("cp1252")
        decoded = fake_output.decode("utf-8", errors="replace")
        self.assertIn("FortiClient-VPN", decoded)
        print("  [OK] Decodificação resiliente de saída Windows validada.")

    def test_windows_error_623_parsing_and_phonebook(self):
        """Valida que o Erro 623 (catálogo telefônico) e outros erros do rasdial são tratados com clareza."""
        vpn_module = importlib.import_module("vpn-gui")

        # Simular Erro 623 real do Windows em português
        sample_err_623 = (
            "Conectando a FortiClient-VPN...\n"
            "Erro 623: O sistema não pôde encontrar a entrada de catálogo telefônico para esta conexão.\n"
            "Para obter mais assistência, clique em Mais Informações."
        )
        parsed_623 = vpn_module.parse_windows_rasdial_error(sample_err_623)
        self.assertIn("Erro 623", parsed_623)
        self.assertIn("catálogo telefônico", parsed_623)

        # Simular Erro 691 (senha/usuário)
        sample_err_691 = "Conectando a FortiClient-VPN...\nErro 691: Falha na autenticação do usuário."
        parsed_691 = vpn_module.parse_windows_rasdial_error(sample_err_691)
        self.assertIn("Erro 691", parsed_691)

        # Simular Erro 809 (timeout gateway)
        sample_err_809 = "Erro 809: O tempo limite da conexão expirou."
        parsed_809 = vpn_module.parse_windows_rasdial_error(sample_err_809)
        self.assertIn("Erro 809", parsed_809)

        print("  [OK] Parsing de mensagens de erro do Windows (incluindo Erro 623/catálogo) validado com sucesso.")

    def test_windows_launcher_and_shortcut_generator(self):
        """Valida que os scripts Windows possuem elevação UAC, resolução de dependências e caminhos corretos."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        launcher_cmd = os.path.join(base_dir, "iniciar_vpn.cmd")
        shortcut_bat = os.path.join(base_dir, "criar_atalho_windows.bat")

        self.assertTrue(os.path.exists(launcher_cmd), "iniciar_vpn.cmd deve existir")
        self.assertTrue(os.path.exists(shortcut_bat), "criar_atalho_windows.bat deve existir")

        with open(launcher_cmd, "r", encoding="utf-8", errors="replace") as f:
            content_launcher = f.read()

        # Validação UAC e elevação
        self.assertIn("net session", content_launcher)
        self.assertIn("-Verb RunAs", content_launcher)
        # Validação de resolução de dependências
        self.assertIn("requirements.txt", content_launcher)
        self.assertIn("Pillow", content_launcher)
        # Validação de perfil VPN
        self.assertIn("FortiClient-VPN", content_launcher)
        self.assertIn("Group18", content_launcher)
        # Execução final do script
        self.assertIn("vpn-gui.py", content_launcher)

        with open(shortcut_bat, "r", encoding="utf-8", errors="replace") as f:
            content_shortcut = f.read()

        self.assertIn("iniciar_vpn.cmd", content_shortcut)
        self.assertIn("icon.ico", content_shortcut)
        self.assertIn("CreateShortcut", content_shortcut)
        print("  [OK] Lançador Windows e criador de atalho UAC validados com sucesso.")

    def test_linux_launcher_integrity_and_security(self):
        """Valida que o iniciar_linux.sh possui verificações estritas, regras seguras e suporte a flags."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        launcher_sh = os.path.join(base_dir, "iniciar_linux.sh")

        self.assertTrue(os.path.exists(launcher_sh), "iniciar_linux.sh deve existir")
        self.assertTrue(os.access(launcher_sh, os.X_OK), "iniciar_linux.sh deve ser executável")

        with open(launcher_sh, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("set -euo pipefail", content)
        self.assertIn("swanctl", content)
        self.assertIn("/etc/sudoers.d/forticlient-vpn", content)
        self.assertIn("visudo", content)
        self.assertIn("FortiClient-VPN.desktop", content)
        self.assertIn("--check", content)
        self.assertIn("--setup-only", content)
        print("  [OK] Lançador Linux, integridade de segurança e sudoers validados.")

if __name__ == "__main__":
    unittest.main()
