from beanie.odm.operators.find.comparison import In
from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.models.cache import Experiment, InstrumentSummary

router = APIRouter(prefix="/instruments", tags=["instruments"])


@router.get("/", response_model=list[InstrumentSummary])
async def read_instruments(current_user: CurrentUser) -> list[InstrumentSummary]:
    """
    Return each distinct non-null instrument together with the number of
    experiments the current user can access under that instrument.
    """
    if current_user.is_superuser:
        base_query = Experiment.find(Experiment.instrument != None)  # noqa: E711
    else:
        user_key = f"uid:{current_user.email}"
        base_query = Experiment.find(
            In(Experiment.players, [user_key]),
            Experiment.instrument != None,  # noqa: E711
        )

    pipeline = [
        {"$group": {"_id": "$instrument", "experiment_count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    results = await base_query.aggregate(pipeline).to_list()
    return [
        InstrumentSummary(instrument=r["_id"], experiment_count=r["experiment_count"])
        for r in results
        if r["_id"] is not None
    ]
