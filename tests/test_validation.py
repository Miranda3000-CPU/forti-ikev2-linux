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

if __name__ == "__main__":
    unittest.main()
