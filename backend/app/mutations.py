import hmac
import re
from fastapi import Depends, Request
from backend.app.auth import COOKIE_NAME, Principal, csrf_token, error, require_operator, require_origin


def require_mutation(request: Request, principal: Principal = Depends(require_operator)):
    require_origin(request)
    if 'control:operate' not in principal.operator.permissions:
        raise error(403, 'ACCESS_DENIED', 'Akun tidak memiliki izin pengaturan.')
    supplied = request.headers.get('x-csrf-token', '')
    if not re.fullmatch(r'[a-f0-9]{64}', supplied) or not hmac.compare_digest(supplied, csrf_token(request.cookies.get(COOKIE_NAME, ''))):
        raise error(403, 'CSRF_REJECTED', 'Sesi halaman berubah; muat ulang.')
    return principal
