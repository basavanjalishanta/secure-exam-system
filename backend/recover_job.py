from models import db

job = db.generation_jobs().find_one({}, sort=[("_id", -1)])
if job and len(job.get("questions", [])) == 20:
    db.generation_jobs().update_one(
        {"_id": job["_id"]},
        {"$set": {"status": "completed", "current_stage": "Question paper generation completed successfully."}}
    )
    existing = db.generated_questions().find_one({"generation_id": job["job_id"]})
    if not existing:
        db.generated_questions().insert_one({
            "generation_id": job["job_id"],
            "subject_id": job["subject_id"],
            "pattern": job["pattern"],
            "questions": job["questions"],
            "created_by": job.get("created_by"),
            "created_at": db.utcnow(),
        })
    print(f"Recovered job {job['job_id']} with all 20 questions successfully!")
else:
    print("No 20-question job found")
