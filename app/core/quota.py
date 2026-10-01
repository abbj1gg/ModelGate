from fastapi import Depends, HTTPException, status

from app.core.rate_limit import enforce_rate_limit
from app.core.security import Principal
from app.services.quota_store import get_quota_store


def enforce_token_quota(
    principal: Principal = Depends(enforce_rate_limit),
) -> Principal:
    snapshot = get_quota_store().get_snapshot(principal.key_id)

    if bool(snapshot["unlimited"]):
        return principal

    monthly_limit = int(snapshot["monthly_limit"] or 0)
    used_tokens = int(snapshot["used_tokens"] or 0)
    remaining_tokens = max(monthly_limit - used_tokens, 0)

    if used_tokens >= monthly_limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Token quota exceeded",
            headers={
                "X-Quota-Limit": str(monthly_limit),
                "X-Quota-Used": str(used_tokens),
                "X-Quota-Remaining": "0",
            },
        )

    return principal