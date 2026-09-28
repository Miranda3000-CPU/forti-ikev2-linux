"""Garantias de distribuição e de licença.

O objetivo do projeto é ser instalável sem compilar, nos dois sistemas, e ser
redistribuível legalmente. Estes testes travam as condições que já quebraram:

  * segredos de produção versionados (PSK/senha em `config/forti.conf`);
  * versão divergente entre o .deb, o instalador Windows e o executável;
  * .deb sem ícone nos temas do sistema (atalho do menu sem ícone);
  * strongSwan (GPLv2) embarcado sem o fonte correspondente;
  * ausência de LICENSE num repositório público.
"""

import os
import re
import subprocess
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

WORKFLOW = os.path.join(".github", "workflows", "build.yml")

# Padrõesmontados em pedaços, de propósito. Se este arquivo trouxesse a
# credencial ou o IP interno por extenso, ele próprio seria o vazamento que a
# varredura abaixo existe para impedir — e o teste se acusaria.
SEGREDOS_CONHECIDOS = ("dticz" + "zambia", "gre." + "dtic.key", "ht." + "dtic.key")
IPS_INTERNOS = ("10.55.1." + "100", "172.16.1." + "7", "10.64.10." + "1")
# Faixas reservadas para documentação (RFC 5737), usadas em código e testes.
IPS_DE_EXEMPLO = ("198.51.100.100", "203.0.113.7")


def read(path):
    with open(os.path.join(BASE_DIR, path), "r", encoding="utf-8") as handle:
        return handle.read()


def exists(path):
    return os.path.exists(os.path.join(BASE_DIR, path))


def git(*args):
    result = subprocess.run(
        ["git", "-C", BASE_DIR] + list(args),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


# As checagens de índice/ignore dependem do .git. Rodar a suíte fora de um
# clone (tarball de fonte, cópia de trabalho) não deve falhar por isso.
IN_GIT_REPO = git("rev-parse", "--git-dir").returncode == 0
requires_git = unittest.skipUnless(
    IN_GIT_REPO, "fora de um repositório git: sem índice para inspecionar"
)


class TestSegredos(unittest.TestCase):
    """config/forti.conf guarda o PSK e a senha reais do gateway."""

    @requires_git
    def test_config_com_credenciais_nao_e_versionado(self):
        self.assertNotIn(
            "config/forti.conf",
            git("ls-files").stdout.split(),
            "config/forti.conf está no índice: contém o PSK e a senha do gateway",
        )

    @requires_git
    def test_config_com_credenciais_esta_ignorado(self):
        ignored = git("check-ignore", "-q", "config/forti.conf")
        self.assertEqual(
            ignored.returncode, 0,
            "config/forti.conf precisa estar no .gitignore",
        )

    def test_ci_barra_segredo_versionado(self):
        """O CI precisa recusar um build com o segredo no índice."""
        self.assertIn("ls-files", read(WORKFLOW))
        self.assertIn("config/forti.conf", read(WORKFLOW))

    @requires_git
    def test_nenhum_credencial_nos_arquivos_rastreados(self):
        """Rede de segurança: PSK/senha reais não podem reaparecer no fonte."""
        rastreados = [
            path for path in git("ls-files").stdout.split()
            if path.endswith((".py", ".sh", ".md", ".conf", ".example",
                              ".iss", ".spec", ".yml", ".bat"))
            and exists(path)
        ]
        for path in rastreados:
            with open(os.path.join(BASE_DIR, path), "r", encoding="utf-8", errors="ignore") as fh:
                conteudo = fh.read()
            for segredo in SEGREDOS_CONHECIDOS:
                self.assertNotIn(
                    segredo, conteudo,
                    "%s contém a credencial que estava exposta" % path,
                )

    def test_ips_internos_nao_vazam(self):
        """Endereços reais foram trocados por faixas de documentação (RFC 5737)."""
        for path in ("vpn_config.py", "vpn-gui.py", "config/forti.conf.example",
                     "tests/test_engine.py", "README.md", "debian/control",
                     "CHANGELOG.md", "tests/test_distribution.py"):
            if not exists(path):
                continue
            conteudo = read(path)
            for ip in IPS_INTERNOS:
                self.assertNotIn(ip, conteudo, "%s ainda traz o IP interno" % path)

    def test_exemplos_usam_faixa_de_documentacao(self):
        """O default do gateway e o modelo de configuração usam faixas RFC 5737."""
        self.assertIn(IPS_DE_EXEMPLO[0], read("vpn_config.py"))
        self.assertIn(IPS_DE_EXEMPLO[0], read("config/forti.conf.example"))


class TestVersao(unittest.TestCase):
    """A versão precisa ter uma fonte só, propagada para os três artefatos."""

    def test_arquivo_version_existe(self):
        self.assertTrue(exists("VERSION"))

    def test_versao_esta_sincronizada(self):
        version = read("VERSION").strip()
        self.assertRegex(version, r"^\d+(\.\d+)+$", "formato de VERSION: %r" % version)
        self.assertIn("AppVersion=%s" % version, read("build/FortiClient-VPN-Setup.iss"))
        self.assertIn("Version: %s" % version, read("debian/control"))

    def test_ci_confere_a_sincronia(self):
        """Sem isso a divergência só aparece quando o usuário reclama."""
        content = read(WORKFLOW)
        self.assertIn("Conferir a sincronia da versão", content)
        self.assertIn("divergiu de VERSION", content)

    def test_gen_build_info_gera_e_propaga(self):
        import build.gen_build_info as gen

        self.assertEqual(gen.resolve_version(), read("VERSION").strip())
        alvos = [alvo[0] for alvo in gen.SYNC_TARGETS]
        self.assertTrue(any("Setup.iss" in a for a in alvos), alvos)
        self.assertTrue(any(a.endswith("debian/control") for a in alvos), alvos)

    def test_gen_build_info_web_url_padrao_vazio(self):
        """O build público não pode embutir painel interno: padrão é vazio."""
        import build.gen_build_info as gen

        salvo = os.environ.pop("FCT_WEB_URL", None)
        try:
            self.assertEqual(gen.resolve_web_url(), "")
        finally:
            if salvo is not None:
                os.environ["FCT_WEB_URL"] = salvo

    def test_gen_build_info_web_url_via_env(self):
        """Build interno (time) define o painel via FCT_WEB_URL, sem IPs no fonte."""
        import build.gen_build_info as gen

        os.environ["FCT_WEB_URL"] = "https://192.0.2.99:10443/"
        try:
            self.assertEqual(gen.resolve_web_url(), "https://192.0.2.99:10443/")
        finally:
            del os.environ["FCT_WEB_URL"]

    def test_ci_exige_tag_igual_a_version(self):
        """Publicar v9.9.9 com VERSION 2.1.2 gera pacote mentiroso."""
        content = read(WORKFLOW)
        self.assertIn("refs/tags/v", content)
        self.assertIn("GITHUB_REF_NAME", content)

    def test_deb_usa_arquivo_all(self):
        """O .deb não tem código compilado: o nome precisa bater com o control."""
        self.assertIn("Architecture: all", read("debian/control"))
        self.assertIn('ARCH="all"', read("build/build_deb.sh"))


class TestPacoteLinux(unittest.TestCase):
    def test_deb_declara_changelog_e_copyright(self):
        """Sem changelog/copyright o apt trata o pacote como órfão."""
        for arquivo in ("debian/changelog", "debian/copyright"):
            self.assertTrue(exists(arquivo), "%s ausente" % arquivo)
        self.assertIn("changelog", read("build/build_deb.sh"))
        self.assertIn("copyright", read("build/build_deb.sh"))

    def test_deb_tem_scripts_de_manutencao_completos(self):
        """postinst+prerm sem postrm deixa atalho e ícone na desinstalação."""
        for script in ("debian/postinst", "debian/prerm", "debian/postrm"):
            self.assertTrue(exists(script), "%s ausente" % script)
        self.assertIn("postrm", read("build/build_deb.sh"))
        # O postinst precisa reconstruir os caches, senão o atalho entra sem
        # ícone e só aparece no login seguinte.
        self.assertIn("gtk-update-icon-cache", read("debian/postinst"))
        self.assertIn("update-desktop-database", read("debian/postinst"))

    def test_deb_instala_icone_nos_temas(self):
        """Sem ícone no hicolor o atalho do menu abre sem imagem."""
        for script in ("build/build_deb.sh", "install.sh"):
            content = read(script)
            self.assertIn("hicolor/256x256/apps", content, script)
            self.assertIn("pixmaps", content, script)

    def test_deb_instala_licencas(self):
        """Quem instala o .deb precisa receber a licença junto."""
        content = read("build/build_deb.sh")
        self.assertIn("LICENSE", content)
        self.assertIn("NOTICE", content)
        self.assertIn("share/doc", content)

    def test_deb_embarca_build_info(self):
        """Sem build_info.py no pacote, o app Linux reporta a versão como 'dev'."""
        self.assertIn("build_info.py", read("build/build_deb.sh"))

    def test_deb_tem_licoes_de_script(self):
        """dpkg -l marca o pacote como 'half-installed' sem isso."""
        self.assertIn("md5sums", read("build/build_deb.sh"))

    def test_artefatos_de_build_nao_sao_versionados(self):
        """`build/deb/` é o staging do .deb: versioná-lo commita o pacote inteiro."""
        ignorados = read(".gitignore")
        for caminho in ("dist/", "build/output", "build/cache", "build/deb/",
                        "build_info.py", "vendor/windows/*.exe"):
            self.assertIn(caminho, ignorados, "%s fora do .gitignore" % caminho)

    @requires_git
    def test_artefatos_de_build_fora_do_indice(self):
        vazando = [
            path for path in git("ls-files").stdout.split()
            if path.startswith(("build/deb/", "dist/", "build/output/", "build/cache/"))
            or path == "build_info.py"
        ]
        self.assertEqual(vazando, [], "artefato de build versionado: %s" % vazando)

    def test_ci_confere_o_icone_do_pacote(self):
        self.assertIn("icons/hicolor/256x256/apps/forticlient-vpn.png", read(WORKFLOW))


class TestDistribuicao(unittest.TestCase):
    def test_workflow_publica_release_em_tag(self):
        """O canal de distribuição é a Release, não o artifact (expira em 90 dias)."""
        content = read(WORKFLOW)
        self.assertIn("gh release create", content)
        self.assertIn("SHA256SUMS", content)
        self.assertIn("download-artifact", content)

    def test_workflow_nao_usa_filtro_de_caminho_em_tag(self):
        """Filtro `paths` também é avaliado em push de tag e cancela a release."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML ausente (instale python3-yaml para checar o workflow)")

        workflow = yaml.safe_load(read(WORKFLOW))
        # PyYAML interpreta a chave `on:` como booleano True (YAML 1.1).
        gatilhos = workflow.get("on", workflow.get(True))
        for evento in ("push", "pull_request"):
            config = gatilhos.get(evento) or {}
            self.assertNotIn(
                "paths", config,
                "`paths` em %s impede o disparo por tag" % evento,
            )

    def test_workflow_tem_permissoes_e_concorrencia(self):
        content = read(WORKFLOW)
        self.assertIn("permissions:", content)
        self.assertIn("concurrency:", content)
        # O padrão é somente-leitura; só a release escreve.
        self.assertRegex(content, r"permissions:\s*\n\s+contents: read")

    def test_readme_orienta_para_a_release(self):
        """'Rode o workflow' exige escrita no repo: não serve para o público."""
        readme = read("README.md").lower()
        self.assertIn("releases/latest", readme)
        self.assertNotIn("actions →", readme)
        self.assertNotIn("run workflow", readme)


class TestLicenca(unittest.TestCase):
    def test_license_existe_e_e_gplv3(self):
        self.assertTrue(exists("LICENSE"), "LICENSE ausente: repositório público sem licença")
        conteudo = read("LICENSE")
        self.assertIn("GNU GENERAL PUBLIC LICENSE", conteudo)
        self.assertIn("Version 3", conteudo)

    def test_versao_da_licenca_e_a_mesma_do_texto(self):
        """Número de versão divergente entre README/LICENSE/NOTICE é confusão."""
        self.assertIn("GPLv3", read("README.md"))
        self.assertIn("GPLv3", read("NOTICE"))

    def test_notice_cobre_a_gplv2_do_strongswan(self):
        """O instalador embarca strongSwan (GPLv2): a obrigação é de fonte."""
        notice = read("NOTICE")
        self.assertIn("GPLv2", notice)
        self.assertIn("SOURCE-OFFER.txt", notice)
        self.assertIn("vendor/windows", notice)

    def test_oferta_escrita_de_fonte_existe(self):
        """GPLv2 §3(b): oferta escrita válida por três anos."""
        self.assertTrue(exists("SOURCE-OFFER.txt"))
        oferta = read("SOURCE-OFFER.txt")
        self.assertIn("três anos", oferta)
        self.assertIn("§3(b)", oferta)

    def test_windows_experimental_nao_publicado(self):
        """Windows ainda não é distruibído: a release só leva o .deb."""
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML ausente (instale python3-yaml para checar o workflow)")
        workflow = yaml.safe_load(read(WORKFLOW))
        windows = workflow["jobs"]["windows"]
        self.assertTrue(windows.get("continue-on-error", False), "Windows deve ser experimental")
        nomes = [str(step.get("name", "")) for step in windows["steps"]]
        self.assertFalse(
            any("upload-artifact" in nome or "Publicar" in nome for nome in nomes),
            "job experimental não pode publicar artefato",
        )
        self.assertEqual(workflow["jobs"]["release"]["needs"], ["deb"])

    def test_se_publicar_exe_exige_tarball_do_strongswan(self):
        """GPLv2 §2: nunca redistança o instalador sem o fonte correspondente."""
        content = read(WORKFLOW)
        self.assertIn("STRONGSWAN_SHA256", content)
        if "FortiClient-VPN-Setup.exe" in content or "windows-installer" in content:
            self.assertIn("strongswan-", content,
                          "reintroduzir o instalador exige voltar com o tarball GPLv2")

    def test_tarball_do_strongswan_bate_com_o_anunciado(self):
        """O SHA-256 no NOTICE é a prova de que o fonte é o upstream íntegro."""
        sha = re.search(r"\| SHA-256\s+\| `([0-9a-f]{64})`", read("NOTICE"))
        self.assertIsNotNone(sha, "NOTICE sem SHA-256 do tarball do strongSwan")
        workflow = read(WORKFLOW)
        self.assertIn(sha.group(1), workflow, "workflow com SHA-256 diferente do NOTICE")

    def test_marcas_fortinet_sao_avisadas(self):
        for arquivo in ("NOTICE", "README.md"):
            conteudo = read(arquivo)
            self.assertIn("Fortinet", conteudo, arquivo)
            self.assertIn("não", conteudo, arquivo)


if __name__ == "__main__":
    unittest.main()
