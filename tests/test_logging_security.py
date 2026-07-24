import gzip
import logging

from knowledgeforge.ai import AIService
from knowledgeforge.logging_config import configure_private_logging


def test_public_research_requires_https(monkeypatch):
    monkeypatch.setattr(
        "knowledgeforge.ai.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 443))],
    )
    assert AIService._public_url("https://example.com/article")
    assert not AIService._public_url("http://example.com/article")
    assert not AIService._public_url("https://user:password@example.com/article")


def test_logs_rotate_and_compress(tmp_path):
    configure_private_logging(tmp_path, max_mb=1, backups=2)
    logger = logging.getLogger("rotation-test")
    payload = "x" * 400_000
    for _ in range(4):
        logger.info(payload)
    for handler in logging.getLogger().handlers:
        handler.flush()

    archives = list(tmp_path.glob("knowledgeforge.log.*.gz"))
    assert archives
    with gzip.open(archives[0], "rt", encoding="utf-8") as compressed:
        assert "rotation-test" in compressed.read()


def test_egress_audit_is_separate(tmp_path):
    from knowledgeforge.logging_config import audit_egress

    configure_private_logging(tmp_path, max_mb=1, backups=2)
    audit_egress("llm_request_started", provider="test", tls=True)
    for handler in logging.getLogger("knowledgeforge.egress").handlers:
        handler.flush()
    content = (tmp_path / "egress-audit.jsonl").read_text(encoding="utf-8")
    assert '"event":"llm_request_started"' in content
    assert '"tls":true' in content
