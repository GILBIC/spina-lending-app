"""Authorized remittance history shows amounts without private wallet evidence."""


def attach_settlement_splits(cursor, rows):
    if not rows:
        return
    cursor.execute("SELECT to_regclass('treasury.collector_settlements') AS relation")
    if cursor.fetchone()["relation"] is None:
        return
    cursor.execute(
        "SELECT s.remittance_id,s.payload,c.payload AS count_payload "
        "FROM treasury.collector_settlements s JOIN treasury.collector_counts c ON c.id=s.count_id "
        "WHERE s.remittance_id=ANY(%s) AND (s.payload->>'authorized_credit_amount')::numeric>0",
        ([row["id"] for row in rows],),
    )
    splits = {}
    for item in cursor.fetchall():
        settlement, count = item["payload"], item["count_payload"]
        splits[item["remittance_id"]] = {
            "gross_obligation": settlement["gross_obligation"],
            "authorized_credit_amount": settlement["authorized_credit_amount"],
            "physical_amount": settlement["physical_amount"],
            "physical_cash_required": count["physical_cash_required"],
            "excess_amount": count["difference"],
        }
    for row in rows:
        if row["id"] in splits:
            row["settlement_split"] = splits[row["id"]]
