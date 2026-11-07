"""Configuração do gunicorn no container: gunicorn -c python:pricetrail.gunicorn_conf 'pricetrail.wsgi:create()'.

1 worker gthread com 4 threads: o Flask abre uma conexão SQLite por request e o banco
tem um escritor por vez. Os logs do gunicorn saem em JSON, como os do app: o acesso no
stdout (sem query string nem corpo), os erros no stderr.
"""
import ipaddress
import os

from gunicorn import glogging

from .client_ip import pick_client_ip
from .logs import JsonFormatter

bind = "0.0.0.0:8000"
workers = 1
worker_class = "gthread"
threads = 4
worker_tmp_dir = "/tmp"  # tmpfs no compose: o sistema de arquivos do container é só leitura
control_socket_disable = True  # o socket de controle do gunicorn não é usado

# Só quem está aqui (a sub-rede da rede `proxy`, onde fica o Traefik) pode mandar
# X-Forwarded-*. Com isso, X-Forwarded-Proto: https vira request.scheme https, e a
# checagem de Origin e o cookie Secure funcionam atrás do proxy. De outro IP, é ignorado.
forwarded_allow_ips = os.environ.get("FORWARDED_ALLOW_IPS") or "127.0.0.1"
secure_scheme_headers = {"X-FORWARDED-PROTO": "https"}

accesslog = "-"  # stdout
errorlog = "-"  # stderr
loglevel = (os.environ.get("LOG_LEVEL") or "INFO").lower()


class JsonLogger(glogging.Logger):
    """Logger do gunicorn com uma linha JSON por evento, no mesmo formato do logger pricetrail."""

    def setup(self, cfg):
        super().setup(cfg)
        formatter = JsonFormatter()
        for log in (self.error_log, self.access_log):
            for handler in log.handlers:
                handler.setFormatter(formatter)

    def access(self, resp, req, environ, request_time):
        if not self.access_log_enabled:
            return
        status = resp.status.split(None, 1)[0] if isinstance(resp.status, str) else resp.status
        self.access_log.info("acesso", extra={
            "method": environ.get("REQUEST_METHOD"),
            "path": environ.get("PATH_INFO"),  # sem a query string
            "status": int(status),
            "duration_ms": round(request_time.total_seconds() * 1000, 1),
            "bytes": getattr(resp, "sent", None),
            "ip": self._client_ip(environ),
        })

    def _client_ip(self, environ):
        """O X-Forwarded-For só vale vindo do proxy confiável; senão, o IP da conexão."""
        peer = environ.get("REMOTE_ADDR") or "unknown"
        if not self._trusted(peer):
            return peer
        ip = pick_client_ip(environ.get("HTTP_X_FORWARDED_FOR"), environ.get("HTTP_X_REAL_IP"))
        return peer if ip == "unknown" else ip

    def _trusted(self, peer):
        allowed = self.cfg.forwarded_allow_ips
        if "*" in allowed:
            return True
        try:
            address = ipaddress.ip_address(peer)
        except ValueError:
            return False
        return any(address in ipaddress.ip_network(net, strict=False) for net in allowed)


logger_class = JsonLogger
