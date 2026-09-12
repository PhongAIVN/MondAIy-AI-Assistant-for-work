import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.deps import get_current_user_id
from src.connectors.base import ConnectorAPIError, Source
from src.connectors.registry import bindings_for_provider, public_source
from src.db import get_db
from src.models.connection import Connection
from src.models.schemas import IntegrationListResponse, IntegrationResponse, IntegrationSourcesResponse, SourceInfo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=IntegrationListResponse)
def list_integrations(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> IntegrationListResponse:
    rows = db.execute(select(Connection).where(Connection.user_id == user_id)).scalars().all()
    return IntegrationListResponse(
        integrations=[IntegrationResponse.model_validate(row, from_attributes=True) for row in rows]
    )


def _get_owned_connection(db: Session, integration_id: int, user_id: str) -> Connection:
    row = db.execute(
        select(Connection).where(Connection.id == integration_id, Connection.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy integration.")
    return row


@router.get("/{integration_id}/sources", response_model=IntegrationSourcesResponse)
async def list_integration_sources(
    integration_id: int,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> IntegrationSourcesResponse:
    connection = _get_owned_connection(db, integration_id, user_id)
    bindings = bindings_for_provider(connection.provider)
    if not bindings:
        warning = f"Provider '{connection.provider}' chưa hỗ trợ list sources."
        logger.info("%s integration %s trả source rỗng có cảnh báo", warning, integration_id)
        return IntegrationSourcesResponse(sources=[], warnings=[warning])

    sources: list[SourceInfo] = []
    errors: list[str] = []
    namespaced = len(bindings) > 1
    successful_connectors = 0
    for binding in bindings:
        try:
            connector_sources: list[Source] = await binding.connector_cls(connection, db).list_sources()
            successful_connectors += 1
        except ConnectorAPIError as exc:
            logger.warning(
                "%s/%s list_sources thất bại cho integration %s: %s",
                connection.provider,
                binding.namespace,
                integration_id,
                exc,
            )
            errors.append(f"{binding.label}: {exc}")
            continue

        for source in connector_sources:
            source_id, source_name = public_source(binding, source.id, source.name, namespaced=namespaced)
            sources.append(SourceInfo(id=source_id, name=source_name, item_count=source.item_count))

    if not successful_connectors:
        detail = "; ".join(errors) or f"Provider '{connection.provider}' không trả về connector khả dụng."
        raise HTTPException(status_code=502, detail=detail)

    return IntegrationSourcesResponse(sources=sources, warnings=errors)
