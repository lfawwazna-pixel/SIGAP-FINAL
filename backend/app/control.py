"""Operator adapter. It never supplies observations, heartbeats, or fabricated plans."""
import asyncio
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
import hmac
import re
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.auth import COOKIE_NAME, Principal, csrf_token, error, require_operator, require_origin
from contracts.control import CommandReceipt, ControlCommand, ControlStatus, OperatorControl


class ControlAdapter:
    def __init__(self, settings, intersection_id):
        self.settings, self.intersection_id = settings, intersection_id
        self.commands = OrderedDict()
        self.lock = asyncio.Lock()

    @property
    def headers(self):
        return {'Authorization': 'Bearer '+self.settings.sigap_control_api_key.get_secret_value()}

    async def status(self, client):
        try:
            response = await client.get('/control')
            response.raise_for_status()
            status = ControlStatus.model_validate(response.json())
            if status.intersection_id != self.intersection_id:
                raise ValueError('Wrong intersection')
            return status
        except (httpx.HTTPError, ValidationError, ValueError):
            raise error(503, 'ATCS_UNAVAILABLE', 'Status kendali ATCS tidak dapat dipastikan.') from None

    async def receipt(self, client, identity):
        try:
            response = await client.get(f'/control/receipts/{identity}', headers=self.headers)
            if response.status_code == 404:
                raise error(404, 'RECEIPT_NOT_FOUND', 'Tanda terima sudah tidak tersedia pada sesi ATCS ini.')
            response.raise_for_status()
            receipt = CommandReceipt.model_validate(response.json())
            if receipt.request_id != identity:
                raise ValueError('Wrong request')
            return receipt
        except (httpx.HTTPError, ValidationError, ValueError):
            raise error(503, 'ATCS_UNAVAILABLE', 'Tanda terima ATCS belum dapat dibaca.') from None

    async def submit(self, client, payload, operator_id):
        fingerprint = (operator_id, payload.model_dump_json())
        # Serialize operator requests, preserving the exact envelope for a retry.
        async with self.lock:
            cached = self.commands.get(payload.request_id)
            if cached:
                if cached[0] != fingerprint:
                    raise error(409, 'REQUEST_ID_REUSED', 'Identitas permintaan sudah digunakan.')
                command = cached[1]
            else:
                status = await self.status(client)
                if status.atcs_run_id != payload.expected_run_id or status.revision != payload.expected_revision:
                    raise error(409, 'STATE_CHANGED', 'Keadaan ATCS berubah. Periksa status terbaru sebelum mencoba lagi.')
                if not status.available or status.sender_id is None:
                    raise error(409, 'NOT_READY', 'Belum ada sumber SIGAP yang siap mengambil kendali.')
                if payload.action == 'activate' and (not status.ready or status.source != 'cctv' or status.state != 'fixed_time'):
                    raise error(409, 'NOT_READY', 'Aktivasi dari dashboard memerlukan sumber CCTV yang siap.')
                if payload.action == 'release' and status.session_id is None:
                    raise error(409, 'NO_SESSION', 'Tidak ada sesi SIGAP untuk dilepas.')
                at = datetime.now(timezone.utc)
                values = dict(request_id=payload.request_id, atcs_run_id=status.atcs_run_id,
                    sender_id=status.sender_id, action=payload.action, issued_at=at,
                    expires_at=at+timedelta(seconds=3), expected_revision=payload.expected_revision)
                if payload.action == 'release':
                    values['session_id'] = status.session_id
                command = ControlCommand(**values)
                self.commands[payload.request_id] = (fingerprint, command)
                while len(self.commands) > 512:
                    self.commands.popitem(last=False)
            try:
                response = await client.post('/control/commands', headers=self.headers,
                                             json=command.model_dump(mode='json', exclude_none=True))
                if response.status_code not in (200, 409):
                    response.raise_for_status()
                receipt = CommandReceipt.model_validate(response.json())
                if (receipt.request_id != command.request_id or receipt.atcs_run_id != command.atcs_run_id
                        or receipt.action != command.action):
                    raise ValueError('Receipt does not match command')
                return receipt
            except (httpx.HTTPError, ValidationError, ValueError):
                raise error(503, 'COMMAND_UNCONFIRMED',
                    'Hasil permintaan belum dapat dipastikan. Periksa tanda terima dan status kendali; jangan menganggapnya berhasil.') from None


router = APIRouter(prefix='/api/control', tags=['Kendali SIGAP–ATCS'])


@router.get('', response_model=ControlStatus, dependencies=[Depends(require_operator)])
async def status(request: Request):
    return await request.app.state.control.status(request.app.state.atcs_client)


@router.get('/receipts/{identity}', response_model=CommandReceipt, dependencies=[Depends(require_operator)])
async def receipt(identity: UUID, request: Request):
    return await request.app.state.control.receipt(request.app.state.atcs_client, identity)


@router.post('/commands', response_model=CommandReceipt, dependencies=[Depends(require_origin)])
async def command(payload: OperatorControl, request: Request, principal: Principal = Depends(require_operator)):
    if 'control:operate' not in principal.operator.permissions:
        raise error(403, 'ACCESS_DENIED', 'Akun tidak memiliki izin pengendalian.')
    supplied = request.headers.get('x-csrf-token', '')
    if not re.fullmatch(r'[a-f0-9]{64}', supplied) or not hmac.compare_digest(supplied, csrf_token(request.cookies.get(COOKIE_NAME, ''))):
        raise error(403, 'CSRF_REJECTED', 'Sesi halaman berubah. Muat ulang sebelum memberi perintah.')
    result = await request.app.state.control.submit(request.app.state.atcs_client, payload, principal.operator.id)
    return JSONResponse(result.model_dump(mode='json'), status_code=409 if result.outcome == 'rejected' else 200)
