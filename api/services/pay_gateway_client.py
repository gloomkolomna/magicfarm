"""Клиент pay-gateway (ProxyPay): подписанные запросы создания заказа и получения
статуса (HMAC-SHA256 от raw body + X-Timestamp), приём 403 test_blocked.
PAY_GATEWAY_URL — база шлюза ВКЛЮЧАЯ /pay (напр., https://belovolovhome.ru/pay)."""

import hashlib
import hmac
import json
import time

import httpx

import config


class PayGatewayError(Exception):
    pass


class PayGatewayBlocked(PayGatewayError):
    pass


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def _headers(body: bytes) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Game-Id": config.PAY_GATEWAY_GAME_ID,
        "X-Timestamp": str(int(time.time())),
        "X-Game-Signature": _sign(body, config.PAY_GATEWAY_API_KEY),
    }


def _request(method: str, path: str, body: bytes = b"") -> dict:
    url = f"{config.PAY_GATEWAY_URL}{path}"
    try:
        resp = httpx.request(
            method, url, content=body, headers=_headers(body),
            timeout=config.PAY_GATEWAY_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise PayGatewayError(f"network error: {type(exc).__name__}: {exc}") from exc
    if resp.status_code == 403:
        try:
            detail = resp.json().get("error", "")
        except ValueError:
            detail = ""
        if detail == "test_blocked":
            raise PayGatewayBlocked("test_blocked")
    if resp.status_code >= 400:
        raise PayGatewayError(f"http {resp.status_code}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise PayGatewayError("bad json from gateway") from exc


def create_order(vk_id: int, amount_kop: int, description: str,
                 receipt_email: str = None) -> dict:
    payload = {
        "vk_id": vk_id,
        "amount_kop": amount_kop,
        "description": description,
    }
    if receipt_email:
        payload["receipt_email"] = receipt_email.strip().lower()
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _request("POST", "/orders", body)


def get_order(transaction_id: str) -> dict:
    return _request("GET", f"/orders/{transaction_id}")
