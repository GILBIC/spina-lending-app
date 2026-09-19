from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import OperationalError, errors

from .account_repository import AccountContext, PostgresAccountRepository
from .auth_api import account_repository_dependency, auth_client_dependency
from .auth_client import SupabaseAuthClient
from .employee_authorization import EmployeeAccessDenied
from .employee_operations import EmployeeConflict
from .employee_operations_models import EmployeeAction
from .employee_operations_repository import PostgresEmployeeOperationsRepository
from .request_auth import authenticated_device_context

LOG = logging.getLogger(__name__)


def employee_operations_repository_dependency():
    return PostgresEmployeeOperationsRepository()


def employee_operations_context(
    auth: Annotated[SupabaseAuthClient, Depends(auth_client_dependency)],
    accounts: Annotated[
        PostgresAccountRepository, Depends(account_repository_dependency)
    ],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_device_id: Annotated[str | None, Header(alias="X-Device-Id")] = None,
) -> AccountContext:
    actor = authenticated_device_context(
        authorization=authorization,
        device_identifier=x_device_id,
        auth=auth,
        accounts=accounts,
    )
    if not set(actor.roles).intersection(("collector", "employee", "management")):
        raise HTTPException(
            403,
            detail={
                "code": "employee_access_denied",
                "message": "An active staff account is required",
            },
        )
    return actor


def _call(operation):
    try:
        return operation()
    except EmployeeAccessDenied as error:
        raise HTTPException(
            403, detail={"code": "employee_access_denied", "message": str(error)}
        ) from error
    except EmployeeConflict as error:
        raise HTTPException(
            409, detail={"code": "employee_conflict", "message": str(error)}
        ) from error
    except (
        errors.UniqueViolation,
        errors.ForeignKeyViolation,
        errors.CheckViolation,
        errors.RaiseException,
    ) as error:
        raise HTTPException(
            409,
            detail={
                "code": "employee_conflict",
                "message": "The identity, period or record conflicts with employee data; refresh and review",
            },
        ) from error
    except (OperationalError, errors.UndefinedTable) as error:
        LOG.warning("Employee private database unavailable: %s", type(error).__name__)
        raise HTTPException(
            503,
            detail={
                "code": "employee_setup_unavailable",
                "message": "Private employee setup is unavailable; no action was confirmed",
            },
        ) from error


def create_employee_operations_router():
    router = APIRouter(
        prefix="/api/v1/employee-operations", tags=["employee-operations"]
    )

    @router.get("/workspace")
    def workspace(
        actor: Annotated[AccountContext, Depends(employee_operations_context)],
        repository: Annotated[
            PostgresEmployeeOperationsRepository,
            Depends(employee_operations_repository_dependency),
        ],
        request_id: Annotated[UUID | None, Query()] = None,
    ):
        return _call(lambda: repository.workspace(actor=actor, request_id=request_id))

    @router.post("/actions")
    def action(
        command: EmployeeAction,
        actor: Annotated[AccountContext, Depends(employee_operations_context)],
        repository: Annotated[
            PostgresEmployeeOperationsRepository,
            Depends(employee_operations_repository_dependency),
        ],
    ):
        return _call(lambda: repository.execute(actor=actor, command=command))

    return router
