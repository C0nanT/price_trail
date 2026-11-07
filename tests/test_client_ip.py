"""pick_client_ip: IP do cliente na cadeia X-Forwarded-For, sem confiar nas faixas da Cloudflare."""
import os
import re
import unittest

from pricetrail.client_ip import CLOUDFLARE_RANGES, pick_client_ip

TRAEFIK_YML = os.environ.get("TRAEFIK_YML", "")


class PickClientIpTests(unittest.TestCase):
    def test_pula_ip_da_cloudflare_no_fim_da_cadeia(self):
        self.assertEqual(
            pick_client_ip("192.0.2.66, 203.0.113.7, 173.245.48.1", None), "203.0.113.7"
        )

    def test_cliente_antes_de_cloudflare(self):
        self.assertEqual(pick_client_ip("203.0.113.7, 173.245.48.1", None), "203.0.113.7")

    def test_cliente_ipv6_com_borda_ipv6_da_cloudflare(self):
        self.assertEqual(
            pick_client_ip("2001:db8::7, 2606:4700:4700::1111", None), "2001:db8::7"
        )

    def test_item_invalido_no_meio_e_pulado(self):
        self.assertEqual(
            pick_client_ip("203.0.113.7, lixo, 173.245.48.1", None), "203.0.113.7"
        )

    def test_cabecalho_vazio_ou_ausente_usa_x_real_ip(self):
        self.assertEqual(pick_client_ip("", "198.51.100.2"), "198.51.100.2")
        self.assertEqual(pick_client_ip(None, "198.51.100.2"), "198.51.100.2")

    def test_sem_cabecalho_nenhum_devolve_unknown(self):
        self.assertEqual(pick_client_ip(None, None), "unknown")
        self.assertEqual(pick_client_ip("", "   "), "unknown")

    def test_todos_os_itens_na_cloudflare_usa_x_real_ip(self):
        self.assertEqual(
            pick_client_ip("173.245.48.1, 104.16.0.1", "198.51.100.2"), "198.51.100.2"
        )

    def test_x_real_ip_e_aparado(self):
        self.assertEqual(pick_client_ip(None, "  198.51.100.2 "), "198.51.100.2")


class CloudflareRangesTests(unittest.TestCase):
    @unittest.skipUnless(
        TRAEFIK_YML and os.path.isfile(TRAEFIK_YML),
        "defina TRAEFIK_YML com o caminho do traefik.yml da borda para conferir",
    )
    def test_lista_confere_com_o_traefik_yml(self):
        with open(TRAEFIK_YML, encoding="utf-8") as arquivo:
            texto = arquivo.read()
        bloco = texto.split("trustedIPs: &ips_cloudflare", 1)[1]
        faixas = []
        for linha in bloco.splitlines()[1:]:
            if linha.strip().startswith("#") or not linha.strip():
                continue
            casou = re.match(r'\s*-\s*"([^"]+)"\s*$', linha)
            if not casou:
                break
            faixas.append(casou.group(1))
        self.assertEqual(list(CLOUDFLARE_RANGES), faixas)

    def test_comentario_de_sincronia_com_a_data(self):
        with open(
            os.path.join(os.path.dirname(__file__), "..", "pricetrail", "client_ip.py"),
            encoding="utf-8",
        ) as arquivo:
            fonte = arquivo.read()
        self.assertIn("traefik.yml", fonte)
        self.assertRegex(fonte, r"\d{4}-\d{2}-\d{2}")
