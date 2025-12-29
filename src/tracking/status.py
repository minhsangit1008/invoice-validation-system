from datetime import datetime


def init_status(invoice_id):
    return {
        "invoice_id": invoice_id,
        "status": "ingested",
        "log": [],
    }


def log_correction(record, field, old_value, new_value, user="system"):
    record["log"].append(
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "correction",
            "user": user,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
        }
    )


def transition_status(record, new_status, user="system"):
    record["log"].append(
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "status_change",
            "user": user,
            "from": record.get("status"),
            "to": new_status,
        }
    )
    record["status"] = new_status
