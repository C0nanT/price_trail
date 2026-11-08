"""Escolhe o IP do cliente a partir da cadeia de proxies. Só biblioteca padrão."""
import ipaddress

# Faixas da Cloudflare. A mesma lista é `trustedIPs: &ips_cloudflare` em
# traefik-default/traefik/traefik.yml e em conan-torres/src/lib/reader/client-ip.ts,
# conferidas em 2026-10-27: as três listas mudam juntas, então atualize todas
# sempre que uma mudar.
CLOUDFLARE_RANGES = (
    # IPv4
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
    # IPv6
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
)

_CLOUDFLARE_NETWORKS = tuple(ipaddress.ip_network(faixa) for faixa in CLOUDFLARE_RANGES)


def _ip_valido(item):
    try:
        return ipaddress.ip_address(item)
    except ValueError:
        return None


def pick_client_ip(x_forwarded_for, x_real_ip):
    """Cliente = o item mais à direita do X-Forwarded-For fora da Cloudflare.

    A Cloudflare acrescenta o IP que viu ao que o cliente mandou, e o Traefik
    acrescenta o da Cloudflare; tudo à esquerda do cliente é controlado por ele.
    Itens inválidos são pulados. Sem item útil, vale o X-Real-IP aparado e,
    por último, 'unknown'.
    """
    for item in reversed((x_forwarded_for or "").split(",")):
        endereco = _ip_valido(item.strip())
        if endereco is None:
            continue
        if any(endereco in rede for rede in _CLOUDFLARE_NETWORKS):
            continue
        return str(endereco)
    return (x_real_ip or "").strip() or "unknown"
