"""Read-only HTTP API for Query MVP results and runtime metadata."""

from __future__ import annotations

from datetime import date
from fastapi import Depends, FastAPI, HTTPException, Query, Response

from .service import QueryReadService


def create_app(service: QueryReadService | None = None) -> FastAPI:
    app = FastAPI(title="XG DB Test Query MVP", version="0.1.0", docs_url="/api/docs", redoc_url=None)

    def get_service() -> QueryReadService:
        return service or QueryReadService.from_environment()

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runs")
    def list_runs(
        current: QueryReadService = Depends(get_service),
        status: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=50, ge=1, le=500),
    ) -> dict:
        try:
            return current.list_runs(status=status, date_from=date_from, date_to=date_to, offset=offset, limit=limit)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str, current: QueryReadService = Depends(get_service)) -> dict:
        try:
            result = current.get_run(run_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="RUN_NOT_FOUND")
        return result

    @app.get("/api/runs/{run_id}/cases")
    def list_cases(
        run_id: str,
        current: QueryReadService = Depends(get_service),
        status: str | None = None,
        feature: str | None = None,
        case_id: str | None = None,
        failure_type: str | None = None,
        sort_by: str | None = None,
        sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
        offset: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> dict:
        try:
            result = current.list_cases(
                run_id,
                status=status,
                feature=feature,
                case_id=case_id,
                failure_type=failure_type,
                sort_by=sort_by,
                sort_dir=sort_dir,
                offset=offset,
                limit=limit,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="RUN_NOT_FOUND")
        return result

    @app.get("/api/runs/{run_id}/cases/{case_id}")
    def get_case(run_id: str, case_id: str, current: QueryReadService = Depends(get_service)) -> dict:
        try:
            result = current.get_case(run_id, case_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="CASE_NOT_FOUND")
        return result

    @app.get("/api/runtime/profile")
    def runtime_profile(current: QueryReadService = Depends(get_service)) -> dict:
        profile = current.runtime_profile()
        if profile is None:
            raise HTTPException(status_code=404, detail="RUNTIME_PROFILE_NOT_CONFIGURED")
        return profile

    @app.get("/api/runtime/contract")
    def contract(current: QueryReadService = Depends(get_service)) -> dict:
        return current.contract()

    @app.get("/api/runtime/types")
    def types(current: QueryReadService = Depends(get_service)) -> dict:
        return current.type_support()

    @app.get("/api/coverage")
    def coverage(current: QueryReadService = Depends(get_service), strategy: str = "pairwise") -> dict:
        try:
            return current.coverage(strategy)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/candidates")
    def list_candidates(current: QueryReadService = Depends(get_service), status: str | None = None) -> dict:
        try:
            return current.list_candidates(status)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/candidates/{case_id}")
    def get_candidate(case_id: str, current: QueryReadService = Depends(get_service)) -> dict:
        try:
            result = current.get_candidate(case_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="CANDIDATE_NOT_FOUND")
        return result

    @app.get("/api/candidates/{case_id}/trial-rows")
    def candidate_trial_rows(
        case_id: str, run: str, step_id: str,
        offset: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=500),
        current: QueryReadService = Depends(get_service),
    ) -> dict:
        try:
            return current.candidate_trial_rows(case_id, run, step_id, offset, limit)
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    @app.get("/api/candidates/{case_id}/artifacts/{kind}")
    def candidate_artifact(case_id: str, kind: str, current: QueryReadService = Depends(get_service)) -> Response:
        try:
            content = current.candidate_artifact(case_id, kind)
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return Response(
            content=content, media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{case_id}-{kind}.json"'},
        )

    return app


app = create_app()
