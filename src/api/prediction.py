"""Bill outcome prediction endpoint."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_session, limiter
from src.prediction.schemas import PredictionFactor, PredictionResponse
from src.prediction.service import is_model_loaded, predict_bill
from src.schemas.common import MetaResponse

router = APIRouter()


@router.get("/bills/{bill_id}/prediction", response_model=PredictionResponse)
@limiter.limit("30/minute")
async def get_bill_prediction(
    request: Request,
    bill_id: str,
    db: AsyncSession = Depends(get_session),
) -> PredictionResponse:
    """Get ML-based committee passage probability for a bill.

    Returns the probability that this bill will clear committee, based on
    current legislative activity (actions, sponsors, session timing).
    Predictions update automatically as bills accumulate more activity.
    """
    if not is_model_loaded():
        raise HTTPException(
            status_code=503,
            detail="Prediction model not loaded. Run promote.py to export model artifacts.",
        )

    result = await predict_bill(db, bill_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    return PredictionResponse(
        bill_id=result["bill_id"],
        committee_passage_probability=result["committee_passage_probability"],
        model_version=result["model_version"],
        key_factors=[PredictionFactor(**f) for f in result["key_factors"]],
        base_rate=result["base_rate"],
        meta=MetaResponse(
            sources=["autoresearch-model"],
            ai_enriched=True,
            ai_model=f"stacking-ensemble-v{result['model_version']}",
        ),
    )
