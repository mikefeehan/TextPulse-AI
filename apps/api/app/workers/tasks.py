from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Contact
from app.services.imports import process_import_record_job
from app.services.analysis_engine import generate_contact_profile
from app.workers.celery_app import celery_app


@celery_app.task(name="textpulse.regenerate_contact_profile")
def regenerate_contact_profile_task(contact_id: str) -> str:
    db = SessionLocal()
    try:
        contact = db.scalar(select(Contact).where(Contact.id == contact_id))
        if contact is None:
            return "missing-contact"
        generate_contact_profile(db, contact)
        db.commit()
        return "ok"
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="textpulse.process_import_record",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def process_import_record_task(
    self,
    import_id: str,
    contact_identifier: str | None = None,
    run_analysis: bool = True,
) -> str:
    return process_import_record_job(
        import_id,
        contact_identifier=contact_identifier,
        run_analysis=run_analysis,
        raise_on_failure=True,
    )
